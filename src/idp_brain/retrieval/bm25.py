"""ParadeDB BM25 candidate retrieval over sanitized chunks."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from time import perf_counter
from typing import Any

from sqlalchemy import Select, and_, exists, func, literal, or_, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from idp_brain.db import MigrationCheckError, assert_pg_search_available
from idp_brain.models import Chunk, ChunkVersion, IndexVersion, Source
from idp_brain.retrieval.models import (
    DEFAULT_RETRIEVAL_CORPUS_ELIGIBILITY_LABELS,
    DEFAULT_RETRIEVAL_LICENSE_POLICY_STATUSES,
    DEFAULT_RETRIEVAL_SENSITIVITY_CLASSES,
    BM25RetrievalProfile,
    Candidate,
    RetrievalFilters,
    RetrievalQuery,
)

logger = logging.getLogger(__name__)


class BM25CandidateRetriever:
    """Retrieve sanitized BM25 candidates using ParadeDB pg_search."""

    def __init__(
        self, session: Session, *, deterministic_fallback: bool = False
    ) -> None:
        self._session = session
        self._deterministic_fallback = deterministic_fallback

    def retrieve(
        self,
        query: RetrievalQuery,
        filters: RetrievalFilters,
        profile: BM25RetrievalProfile | None = None,
        limit: int | None = None,
    ) -> list[Candidate]:
        """Return BM25 candidates after trusted SQL-side filtering."""

        active_profile = profile or BM25RetrievalProfile()
        top_k = limit if limit is not None else active_profile.candidate_limit
        if top_k <= 0:
            return []

        started_at = perf_counter()
        scoped_filters = self._filters_with_active_index_scope(filters)
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
    ) -> RetrievalFilters:
        if filters.active_index_version_id is None:
            return filters

        index_version = self._session.get(IndexVersion, filters.active_index_version_id)
        if index_version is None:
            return filters.model_copy(update={"source_ids": ("__no_matching_index__",)})

        scoped_source_ids = tuple(index_version.source_scope.get("source_ids") or ())
        if not scoped_source_ids:
            return filters
        if filters.source_ids:
            scoped_source_ids = tuple(
                source_id
                for source_id in filters.source_ids
                if source_id in scoped_source_ids
            )
            if not scoped_source_ids:
                scoped_source_ids = ("__no_matching_index__",)
        return filters.model_copy(update={"source_ids": scoped_source_ids})

    def _filtered_count(self, filters: RetrievalFilters) -> int:
        return int(
            self._session.execute(
                select(func.count())
                .select_from(Chunk)
                .where(and_(*self._filter_clauses(filters)))
            ).scalar_one()
        )

    def _filter_clauses(self, filters: RetrievalFilters) -> list[Any]:
        current_chunk = exists(
            select(literal(1)).where(
                ChunkVersion.chunk_id == Chunk.id,
                ChunkVersion.is_current.is_(True),
            )
        )
        clauses = [
            Chunk.source_allowlisted.is_(True),
            Chunk.source_version_id.is_not(None),
            Chunk.sanitized_text != "",
            current_chunk,
        ]
        if filters.source_ids:
            clauses.append(Chunk.source_id.in_(filters.source_ids))
        if filters.source_types:
            clauses.append(Chunk.source_type.in_(filters.source_types))
        if filters.version_labels:
            clauses.append(Chunk.version_label.in_(filters.version_labels))
        if filters.visibility_labels:
            clauses.append(Chunk.visibility_label.in_(filters.visibility_labels))
        sensitivity_classes = (
            filters.sensitivity_classes or DEFAULT_RETRIEVAL_SENSITIVITY_CLASSES
        )
        license_policy_statuses = (
            filters.license_policy_statuses or DEFAULT_RETRIEVAL_LICENSE_POLICY_STATUSES
        )
        corpus_eligibility_labels = (
            filters.corpus_eligibility_labels
            or DEFAULT_RETRIEVAL_CORPUS_ELIGIBILITY_LABELS
        )
        clauses.append(Chunk.sensitivity_class.in_(sensitivity_classes))
        clauses.append(Chunk.license_policy_status.in_(license_policy_statuses))
        if filters.license_ids:
            clauses.append(Chunk.license_id.in_(filters.license_ids))
        if filters.redaction_statuses:
            clauses.append(Chunk.redaction_status.in_(filters.redaction_statuses))
        clauses.append(Chunk.corpus_eligibility_label.in_(corpus_eligibility_labels))
        return clauses

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
            column = getattr(Chunk, field_name)
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
        return (
            select(Chunk.id.label("chunk_id"))
            .where(and_(*self._filter_clauses(filters)))
            .cte("filtered_chunks")
            .prefix_with("MATERIALIZED", dialect="postgresql")
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
        return [getattr(Chunk, field).op("|||")(query_text) for field in fields]

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


def _case(whens: Sequence[tuple[Any, Any]], else_: Any) -> Any:
    from sqlalchemy import case

    return case(*whens, else_=else_)
