"""Exact and bounded fuzzy lookup over sanitized chunks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Select, String, and_, cast, exists, func, literal, or_, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from idp_brain.models import Chunk, ChunkVersion, IndexVersion, Source
from idp_brain.retrieval.models import (
    DEFAULT_RETRIEVAL_CORPUS_ELIGIBILITY_LABELS,
    DEFAULT_RETRIEVAL_LICENSE_POLICY_STATUSES,
    DEFAULT_RETRIEVAL_SENSITIVITY_CLASSES,
    Candidate,
    RetrievalFilters,
    RetrievalPath,
    RetrievalQuery,
)
from idp_brain.retrieval.profiles import ExactRetrievalProfile
from idp_brain.retrieval.query_intent import parse_query_intent

EXACT_FIELD_PRIORITY: Mapping[str, int] = {
    "symbol_path": 10,
    "artifact_path": 20,
    "structure_path": 30,
    "heading_path": 40,
    "signature_text": 50,
    "version_label": 60,
    "sanitized_text": 70,
}
DEFAULT_EXACT_FIELDS = tuple(EXACT_FIELD_PRIORITY)
METADATA_EXACT_FIELD_PRIORITY: Mapping[str, int] = {
    "endpoint_path": 15,
    "schema_key": 25,
    "schema_path": 26,
    "field_name": 27,
    "flag_name": 28,
    "method_name": 29,
    "function_name": 30,
    "error_string": 31,
    "import_path": 32,
    "commit_sha": 33,
    "release_tag": 34,
    "first_seen_version": 35,
    "last_seen_version": 36,
    "claim_subject": 37,
    "claim_predicate": 38,
    "citation_id": 39,
    "tracked_ref": 41,
    "change_summary": 65,
}


class ExactLookupRetriever:
    """Retrieve sanitized chunk candidates using exact metadata lookup."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def retrieve(
        self,
        query: RetrievalQuery,
        filters: RetrievalFilters,
        profile: ExactRetrievalProfile | None = None,
        limit: int = 20,
    ) -> list[Candidate]:
        """Return deterministic exact candidates after trusted filtering."""

        active_profile = profile or ExactRetrievalProfile(
            profile_id="exact_default",
            exact_fields=DEFAULT_EXACT_FIELDS,
            candidate_limit=limit,
        )
        top_k = min(limit, active_profile.candidate_limit)
        if top_k <= 0:
            return []
        if (
            active_profile.require_active_index
            and filters.active_index_version_id is None
        ):
            raise ValueError(
                "exact retrieval profile requires active_index_version filtering"
            )

        intent = parse_query_intent(query.query_text)
        scoped_filters = self._filters_with_active_index_scope(filters)
        filtered_chunks = self._filtered_chunk_scope(
            scoped_filters,
            active_profile.exact_fields,
        ).cte("filtered_chunks")
        field_terms = _field_terms_for_profile(
            intent.field_terms(),
            active_profile.exact_fields,
        )

        exact_rows = self._session.execute(
            self._exact_select(filtered_chunks, field_terms, top_k)
        ).mappings()
        candidates = [
            self._candidate_from_row(row, rank=index + 1, retrieval_path="exact")
            for index, row in enumerate(exact_rows)
        ]
        if candidates or not query.enable_fuzzy:
            return candidates

        fuzzy_rows = self._session.execute(
            self._fuzzy_select(filtered_chunks, intent.fuzzy_terms, top_k)
        ).mappings()
        return [
            self._candidate_from_row(row, rank=index + 1, retrieval_path="fuzzy")
            for index, row in enumerate(fuzzy_rows)
        ]

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

    def _filtered_chunk_scope(
        self,
        filters: RetrievalFilters,
        exact_fields: Sequence[str],
    ) -> Select[tuple[Any, ...]]:
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

        metadata_fields = [
            Chunk.metadata_[field_name].as_string().label(field_name)
            for field_name in exact_fields
            if not hasattr(Chunk, field_name)
        ]

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
            Chunk.sanitized_text,
            Chunk.language,
            Chunk.artifact_role,
            Chunk.chunk_kind,
            Chunk.visibility_label,
            Chunk.sensitivity_class,
            Chunk.license_policy_status,
            Chunk.license_id,
            Chunk.redaction_status,
            Chunk.corpus_eligibility_label,
            Chunk.first_seen_at,
            select(Source.authority_rank)
            .where(Source.id == Chunk.source_id)
            .scalar_subquery()
            .label("authority_rank"),
            *metadata_fields,
        ).where(and_(*clauses))

    def _exact_select(
        self,
        filtered_chunks: Any,
        field_terms: Mapping[str, Sequence[str]],
        limit: int,
    ) -> Select[tuple[Any, ...]]:
        field_matches: list[Any] = []
        field_labels: list[Any] = []
        field_priority: list[Any] = []

        for field_name, terms in field_terms.items():
            if not terms:
                continue
            column = filtered_chunks.c[field_name]
            if field_name == "structure_path":
                term_clauses = [
                    func.lower(cast(column, String)).contains(term.lower())
                    for term in terms
                ]
            elif (
                field_name in {"sanitized_text", "signature_text", "heading_path"}
                or field_name in METADATA_EXACT_FIELD_PRIORITY
            ):
                term_clauses = [
                    func.lower(column).contains(term.lower()) for term in terms
                ]
            else:
                term_clauses = [func.lower(column) == term.lower() for term in terms]
            match_clause = or_(*term_clauses)
            field_matches.append(match_clause)
            field_labels.append((match_clause, field_name))
            field_priority.append((match_clause, _field_priority(field_name)))

        if not field_matches:
            return self._empty_select(filtered_chunks)

        priority_expr = _case(field_priority, 999).label("field_priority")
        matched_field_expr = _case(field_labels, "unknown").label("matched_field")
        path_specificity = func.length(
            func.coalesce(filtered_chunks.c.artifact_path, "")
        ).label("path_specificity")
        authority_rank = func.coalesce(filtered_chunks.c.authority_rank, 1000).label(
            "authority_rank"
        )

        return (
            select(
                filtered_chunks,
                priority_expr,
                matched_field_expr,
                path_specificity,
                authority_rank,
            )
            .where(or_(*field_matches))
            .order_by(
                priority_expr.asc(),
                authority_rank.asc(),
                filtered_chunks.c.version_label.desc().nullslast(),
                path_specificity.desc(),
                filtered_chunks.c.chunk_id.asc(),
            )
            .limit(limit)
        )

    def _fuzzy_select(
        self,
        filtered_chunks: Any,
        terms: Sequence[str],
        limit: int,
    ) -> Select[tuple[Any, ...]]:
        if not terms:
            return self._empty_select(filtered_chunks)
        path_specificity = func.length(
            func.coalesce(filtered_chunks.c.artifact_path, "")
        ).label("path_specificity")
        authority_rank = func.coalesce(filtered_chunks.c.authority_rank, 1000).label(
            "authority_rank"
        )
        fuzzy_clauses = self._fuzzy_clauses(filtered_chunks, terms)
        return (
            select(
                filtered_chunks,
                literal(900).label("field_priority"),
                literal("metadata_fuzzy").label("matched_field"),
                path_specificity,
                authority_rank,
            )
            .where(or_(*fuzzy_clauses))
            .order_by(
                authority_rank.asc(),
                filtered_chunks.c.version_label.desc().nullslast(),
                path_specificity.desc(),
                filtered_chunks.c.chunk_id.asc(),
            )
            .limit(limit)
        )

    def _fuzzy_clauses(self, filtered_chunks: Any, terms: Sequence[str]) -> list[Any]:
        fuzzy_fields = (
            filtered_chunks.c.symbol_path,
            filtered_chunks.c.artifact_path,
            filtered_chunks.c.heading_path,
        )
        bind = self._session.get_bind()
        if bind.dialect.name == "postgresql":
            return [
                or_(*(field.op("%")(term) for field in fuzzy_fields)) for term in terms
            ]
        return [
            or_(*(func.lower(field).contains(term.lower()) for field in fuzzy_fields))
            for term in terms
        ]

    def _empty_select(self, filtered_chunks: Any) -> Select[tuple[Any, ...]]:
        return select(
            filtered_chunks,
            literal(999).label("field_priority"),
            literal("none").label("matched_field"),
            literal(0).label("path_specificity"),
            literal(1000).label("authority_rank"),
        ).where(literal(False))

    def _candidate_from_row(
        self,
        row: RowMapping,
        *,
        rank: int,
        retrieval_path: RetrievalPath,
    ) -> Candidate:
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
            retrieval_path=retrieval_path,
            rank=rank,
            matched_fields=(row["matched_field"],),
            metadata=metadata,
            diagnostics={
                "field_priority": row["field_priority"],
                "authority_rank": row["authority_rank"],
                "path_specificity": row["path_specificity"],
            },
        )


def _case(whens: Sequence[tuple[Any, Any]], else_: Any) -> Any:
    from sqlalchemy import case

    return case(*whens, else_=else_)


def _field_terms_for_profile(
    parsed_field_terms: Mapping[str, Sequence[str]],
    exact_fields: Sequence[str],
) -> dict[str, tuple[str, ...]]:
    field_terms = {
        field_name: tuple(parsed_field_terms.get(field_name, ()))
        for field_name in exact_fields
    }
    raw_terms = tuple(
        term for terms in parsed_field_terms.values() for term in terms if term
    )
    for field_name in exact_fields:
        if field_name in parsed_field_terms:
            continue
        if field_name in METADATA_EXACT_FIELD_PRIORITY:
            field_terms[field_name] = raw_terms
    return {field_name: terms for field_name, terms in field_terms.items() if terms}


def _field_priority(field_name: str) -> int:
    return EXACT_FIELD_PRIORITY.get(
        field_name,
        METADATA_EXACT_FIELD_PRIORITY.get(field_name, 80),
    )
