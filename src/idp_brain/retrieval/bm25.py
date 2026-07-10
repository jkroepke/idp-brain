"""ParadeDB BM25 candidate retrieval over sanitized chunks."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from time import perf_counter
from typing import Any

from sqlalchemy import Select, func, literal, or_, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from idp_brain.db import MigrationCheckError, assert_pg_search_available
from idp_brain.models import Chunk, Source
from idp_brain.retrieval.corpus_filters import (
    TrustedCorpusScope,
    build_filtered_chunk_scope,
    chunk_filter_clauses,
    resolve_active_index_filters,
)
from idp_brain.retrieval.models import (
    BM25RetrievalProfile,
    Candidate,
    RetrievalFilters,
    RetrievalQuery,
)

logger = logging.getLogger(__name__)


class BM25CandidateRetriever:
    """Retrieve sanitized BM25 candidates using ParadeDB pg_search."""

    def __init__(
        self,
        session: Session,
        *,
        deterministic_fallback: bool = False,
        trusted_scope: TrustedCorpusScope,
    ) -> None:
        self._session = session
        self._deterministic_fallback = deterministic_fallback
        self._trusted_scope = trusted_scope

    def retrieve(
        self,
        query: RetrievalQuery,
        filters: RetrievalFilters,
        profile: BM25RetrievalProfile | None = None,
        limit: int | None = None,
    ) -> list[Candidate]:
        """Return BM25 candidates after trusted SQL-side filtering."""

        active_profile = profile or BM25RetrievalProfile()
        top_k = _candidate_limit(limit, active_profile.candidate_limit)
        if filters.active_index_version_id is None:
            raise ValueError(
                "BM25 retrieval profile requires active_index_version filtering"
            )

        started_at = perf_counter()
        scoped_filters = self._filters_with_active_index_scope(filters, active_profile)
        filtered_count = self._filtered_count(scoped_filters)

        bind = self._session.get_bind()
        if bind.dialect.name == "postgresql" and not self._deterministic_fallback:
            assert_pg_search_available(self._session.connection())
            rows = self._session.execute(
                self._postgres_bm25_select(
                    query.query_text,
                    scoped_filters,
                    active_profile,
                    top_k,
                )
            ).mappings()
        elif self._deterministic_fallback:
            rows = self._session.execute(
                self._fallback_select(
                    query.query_text,
                    scoped_filters,
                    active_profile,
                    top_k,
                )
            ).mappings()
        else:
            raise MigrationCheckError(
                "BM25 retrieval requires PostgreSQL with the pg_search extension; "
                "use deterministic_fallback only in SQL/unit tests."
            )

        candidates = [
            self._candidate_from_row(row, rank=index + 1)
            for index, row in enumerate(rows)
        ]
        logger.info(
            "bm25 retrieval completed",
            extra={
                "query_length": len(query.query_text),
                "profile_id": active_profile.profile_id,
                "filtered_candidate_count": filtered_count,
                "latency_ms": round((perf_counter() - started_at) * 1000, 3),
            },
        )
        return candidates

    def _filters_with_active_index_scope(
        self,
        filters: RetrievalFilters,
        profile: BM25RetrievalProfile,
    ) -> RetrievalFilters:
        return resolve_active_index_filters(
            self._session,
            filters,
            required=True,
            expected_kind="bm25",
            expected_profile=profile.profile_id
            if profile.require_active_index
            else None,
        )

    def _filtered_count(self, filters: RetrievalFilters) -> int:
        return int(
            self._session.execute(
                select(func.count()).select_from(self._filtered_chunk_scope(filters))
            ).scalar_one()
        )

    def _filter_clauses(self, filters: RetrievalFilters) -> list[Any]:
        return chunk_filter_clauses(self._session, filters, self._trusted_scope)

    def _postgres_bm25_select(
        self,
        query_text: str,
        filters: RetrievalFilters,
        profile: BM25RetrievalProfile,
        limit: int,
    ) -> Select[tuple[Any, ...]]:
        filtered_chunks = self._filtered_chunk_scope(filters)
        bm25_score = func.pdb.score(Chunk.id).label("bm25_score")
        predicates = self._bm25_predicates(query_text, profile.bm25_fields)
        matched_fields = _matched_fields_expression(
            zip(predicates, profile.bm25_fields, strict=True)
        ).label("matched_fields")
        return (
            self._base_chunk_select(
                bm25_score,
                matched_fields,
            )
            .join(filtered_chunks, filtered_chunks.c.chunk_id == Chunk.id)
            .where(or_(*predicates))
            .order_by(bm25_score.desc(), Chunk.id.asc())
            .limit(limit)
        )

    def _fallback_select(
        self,
        query_text: str,
        filters: RetrievalFilters,
        profile: BM25RetrievalProfile,
        limit: int,
    ) -> Select[tuple[Any, ...]]:
        filtered_chunks = self._filtered_chunk_scope(filters)
        lowered_query = query_text.lower()
        score_terms: list[Any] = []
        match_clauses: list[Any] = []
        for field_name in profile.bm25_fields:
            column = _bm25_field_expression(field_name)
            field_text = func.lower(func.coalesce(column, ""))
            match_clause = field_text.contains(lowered_query)
            match_clauses.append(match_clause)
            score_terms.append((match_clause, 1.0))

        bm25_score = _case(score_terms, 0.0).label("bm25_score")
        matched_fields = _matched_fields_expression(
            zip(match_clauses, profile.bm25_fields, strict=True)
        ).label("matched_fields")
        return (
            self._base_chunk_select(bm25_score, matched_fields)
            .join(filtered_chunks, filtered_chunks.c.chunk_id == Chunk.id)
            .where(or_(*match_clauses))
            .order_by(bm25_score.desc(), Chunk.id.asc())
            .limit(limit)
        )

    def _filtered_chunk_scope(self, filters: RetrievalFilters) -> Any:
        return build_filtered_chunk_scope(
            self._session, filters, trusted=self._trusted_scope
        )

    def _base_chunk_select(
        self,
        bm25_score: Any,
        matched_fields: Any,
    ) -> Select[tuple[Any, ...]]:
        authority_rank = (
            select(Source.authority_rank)
            .where(Source.id == Chunk.source_id)
            .scalar_subquery()
            .label("authority_rank")
        )
        return select(
            Chunk.id.label("chunk_id"),
            Chunk.source_id,
            Chunk.source_version_id,
            Chunk.source_type,
            Chunk.version_label,
            Chunk.artifact_path,
            Chunk.heading_path,
            Chunk.structure_path,
            Chunk.symbol_path,
            Chunk.signature_text,
            Chunk.language,
            Chunk.artifact_role,
            Chunk.chunk_kind,
            Chunk.visibility_label,
            Chunk.sensitivity_class,
            Chunk.license_policy_status,
            Chunk.license_id,
            Chunk.redaction_status,
            Chunk.corpus_eligibility_label,
            authority_rank,
            bm25_score,
            matched_fields,
        )

    def _bm25_predicates(
        self,
        query_text: str,
        fields: Sequence[str],
    ) -> list[Any]:
        return [_bm25_field_expression(field).op("|||")(query_text) for field in fields]

    def _candidate_from_row(self, row: RowMapping, *, rank: int) -> Candidate:
        metadata = {
            "source_id": row["source_id"],
            "source_version_id": row["source_version_id"],
            "source_type": row["source_type"],
            "version_label": row["version_label"],
            "artifact_path": row["artifact_path"],
            "heading_path": row["heading_path"],
            "structure_path": row["structure_path"],
            "symbol_path": row["symbol_path"],
            "signature_text": row["signature_text"],
            "language": row["language"],
            "artifact_role": row["artifact_role"],
            "chunk_kind": row["chunk_kind"],
            "visibility_label": row["visibility_label"],
            "sensitivity_class": row["sensitivity_class"],
            "license_policy_status": row["license_policy_status"],
            "license_id": row["license_id"],
            "redaction_status": row["redaction_status"],
            "corpus_eligibility_label": row["corpus_eligibility_label"],
        }
        return Candidate(
            chunk_id=row["chunk_id"],
            retrieval_path="bm25",
            rank=rank,
            matched_fields=_matched_fields(row["matched_fields"]),
            metadata=metadata,
            diagnostics={
                "bm25_score": float(row["bm25_score"]),
                "authority_rank": row["authority_rank"],
            },
        )


def _matched_fields(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        if "," in value:
            return tuple(field for field in value.split(",") if field)
        return (value,)
    return tuple(str(field) for field in value)


def _matched_fields_expression(
    field_predicates: Iterable[tuple[Any, str]],
) -> Any:
    expression = literal("")
    for predicate, field_name in field_predicates:
        expression += _case([(predicate, f"{field_name},")], "")
    return expression


def _bm25_field_expression(field_name: str) -> Any:
    if hasattr(Chunk, field_name):
        return getattr(Chunk, field_name)
    return Chunk.metadata_[field_name].as_string()


def _case(whens: Sequence[tuple[Any, Any]], else_: Any) -> Any:
    from sqlalchemy import case

    return case(*whens, else_=else_)


def _candidate_limit(override: int | None, profile_limit: int) -> int:
    limit = profile_limit if override is None else override
    if not 50 <= limit <= 200:
        raise ValueError("BM25 candidate limit must be between 50 and 200")
    return limit
