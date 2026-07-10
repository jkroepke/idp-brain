"""pgvector candidate retrieval over sanitized chunk embeddings."""

from __future__ import annotations

import hashlib
import logging
import math
from time import perf_counter
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pgvector.sqlalchemy import VECTOR  # type: ignore[import-untyped]
from sqlalchemy import (
    Select,
    and_,
    cast,
    exists,
    func,
    literal,
    literal_column,
    select,
    text,
)
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from idp_brain.db import MigrationCheckError, assert_vector_available
from idp_brain.embeddings import (
    EmbeddingInput,
    EmbeddingProviderRegistry,
)
from idp_brain.ingestion.runs import sanitize_diagnostic_text
from idp_brain.models import (
    Chunk,
    ChunkVersion,
    Embedding,
    EmbeddingModel,
    IndexVersion,
    Source,
)
from idp_brain.retrieval.models import (
    DEFAULT_RETRIEVAL_CORPUS_ELIGIBILITY_LABELS,
    DEFAULT_RETRIEVAL_LICENSE_POLICY_STATUSES,
    DEFAULT_RETRIEVAL_SENSITIVITY_CLASSES,
    Candidate,
    RetrievalFilters,
    RetrievalQuery,
    VectorRetrievalProfile,
)

logger = logging.getLogger(__name__)
HNSW_INDEXED_DIMENSIONS = frozenset({32, 64})


class VectorCandidateRetriever:
    """Retrieve sanitized vector candidates using configured query embeddings."""

    def __init__(
        self,
        session: Session,
        *,
        provider_registry: EmbeddingProviderRegistry,
        deterministic_fallback: bool = False,
    ) -> None:
        self._session = session
        self._provider_registry = provider_registry
        self._deterministic_fallback = deterministic_fallback

    def retrieve(
        self,
        query: RetrievalQuery,
        filters: RetrievalFilters,
        profile: VectorRetrievalProfile,
        limit: int | None = None,
    ) -> list[Candidate]:
        """Return vector candidates after trusted SQL-side filtering."""

        top_k = limit if limit is not None else profile.candidate_limit
        if top_k <= 0:
            return []

        started_at = perf_counter()
        embedding_model = self._active_embedding_model(profile)
        if embedding_model is None:
            return []
        if not self._active_index_matches_model(profile):
            return []

        provider = self._provider_registry.resolve(profile.embedding_profile_id)
        query_input = _query_embedding_input(query, filters, profile)
        query_vector = provider.embed([query_input])[0]
        if query_vector.dimensions != provider.dimensions:
            raise ValueError("query embedding provider returned unexpected dimensions")
        if query_vector.dimensions != embedding_model.dimensions:
            raise ValueError("query embedding dimensions do not match active model")

        scoped_filters = self._filters_with_active_index_scope(filters, profile)
        filtered_count = self._filtered_count(scoped_filters)
        retrieval_strategy = _retrieval_strategy(filtered_count, profile)

        bind = self._session.get_bind()
        if bind.dialect.name == "postgresql" and not self._deterministic_fallback:
            assert_vector_available(self._session.connection())
            if retrieval_strategy == "hnsw":
                self._session.execute(
                    text("SET LOCAL hnsw.ef_search = :ef_search"),
                    {"ef_search": profile.hnsw_ef_search},
                )
            rows = self._session.execute(
                self._postgres_vector_select(
                    query_vector.values,
                    scoped_filters,
                    profile,
                    top_k,
                    retrieval_strategy=retrieval_strategy,
                )
            ).mappings()
            candidates = [
                self._candidate_from_row(
                    row,
                    rank=index + 1,
                    retrieval_strategy=retrieval_strategy,
                )
                for index, row in enumerate(rows)
            ]
        elif self._deterministic_fallback:
            rows = self._session.execute(
                self._fallback_scope_select(
                    scoped_filters,
                    profile,
                    dimensions=query_vector.dimensions,
                )
            ).mappings()
            candidates = self._fallback_candidates(
                rows,
                query_vector=query_vector.values,
                limit=top_k,
                retrieval_strategy=retrieval_strategy,
            )
        else:
            raise MigrationCheckError(
                "Vector retrieval requires PostgreSQL with the vector extension; "
                "use deterministic_fallback only in SQL/unit tests."
            )

        logger.info(
            "vector retrieval completed",
            extra={
                "query_hash": query_input.sanitized_content_hash,
                "profile_id": profile.profile_id,
                "embedding_profile_id": profile.embedding_profile_id,
                "embedding_model_id": profile.embedding_model_id,
                "index_version_id": profile.index_version_id,
                "dimensions": query_vector.dimensions,
                "filtered_candidate_count": filtered_count,
                "latency_ms": round((perf_counter() - started_at) * 1000, 3),
            },
        )
        return candidates

    def _filters_with_active_index_scope(
        self,
        filters: RetrievalFilters,
        profile: VectorRetrievalProfile,
    ) -> RetrievalFilters:
        index_version = self._session.get(IndexVersion, profile.index_version_id)
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

    def _active_embedding_model(
        self,
        profile: VectorRetrievalProfile,
    ) -> EmbeddingModel | None:
        model = self._session.get(EmbeddingModel, profile.embedding_model_id)
        if model is None:
            return None
        if model.promotion_status in {"inactive", "retired"}:
            return None
        return model

    def _active_index_matches_model(
        self,
        profile: VectorRetrievalProfile,
    ) -> bool:
        index_version = self._session.get(IndexVersion, profile.index_version_id)
        if index_version is None:
            return False
        return (
            index_version.status == "active"
            and index_version.embedding_model_id == profile.embedding_model_id
        )

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
                ChunkVersion.tombstoned_at.is_(None),
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

    def _filtered_chunk_scope(self, filters: RetrievalFilters) -> Any:
        authority_rank = (
            select(Source.authority_rank)
            .where(Source.id == Chunk.source_id)
            .scalar_subquery()
            .label("authority_rank")
        )
        return (
            select(
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
            )
            .where(and_(*self._filter_clauses(filters)))
            .cte("filtered_chunks")
            .prefix_with("MATERIALIZED", dialect="postgresql")
        )

    def _postgres_vector_select(
        self,
        query_vector: list[float],
        filters: RetrievalFilters,
        profile: VectorRetrievalProfile,
        limit: int,
        retrieval_strategy: str,
    ) -> Select[tuple[Any, ...]]:
        filtered_chunks = self._filtered_chunk_scope(filters)
        distance = self._distance_expression(
            query_vector,
            retrieval_strategy=retrieval_strategy,
        ).label("distance")
        return (
            select(
                filtered_chunks,
                Embedding.chunk_id,
                Embedding.embedding_model_id,
                Embedding.index_version_id,
                distance,
            )
            .select_from(Embedding)
            .join(filtered_chunks, filtered_chunks.c.chunk_id == Embedding.chunk_id)
            .where(
                Embedding.embedding_model_id == profile.embedding_model_id,
                Embedding.index_version_id == profile.index_version_id,
                Embedding.is_active.is_(True),
                self._dimensions_predicate(
                    len(query_vector),
                    retrieval_strategy=retrieval_strategy,
                ),
            )
            .order_by(distance.asc(), Embedding.chunk_id.asc())
            .limit(limit)
        )

    def _distance_expression(
        self,
        query_vector: list[float],
        *,
        retrieval_strategy: str,
    ) -> Any:
        dimensions = len(query_vector)
        if retrieval_strategy == "hnsw" and dimensions in HNSW_INDEXED_DIMENSIONS:
            return cast(Embedding.vector, VECTOR(dimensions)).cosine_distance(
                query_vector
            )
        return Embedding.vector.cosine_distance(query_vector)

    def _dimensions_predicate(
        self,
        dimensions: int,
        *,
        retrieval_strategy: str,
    ) -> Any:
        if retrieval_strategy == "hnsw" and dimensions in HNSW_INDEXED_DIMENSIONS:
            return Embedding.dimensions == literal_column(str(dimensions))
        return Embedding.dimensions == dimensions

    def _fallback_scope_select(
        self,
        filters: RetrievalFilters,
        profile: VectorRetrievalProfile,
        *,
        dimensions: int,
    ) -> Select[tuple[Any, ...]]:
        filtered_chunks = self._filtered_chunk_scope(filters)
        return (
            select(
                filtered_chunks,
                Embedding.chunk_id,
                Embedding.embedding_model_id,
                Embedding.index_version_id,
                Embedding.vector,
            )
            .select_from(Embedding)
            .join(filtered_chunks, filtered_chunks.c.chunk_id == Embedding.chunk_id)
            .where(
                Embedding.embedding_model_id == profile.embedding_model_id,
                Embedding.index_version_id == profile.index_version_id,
                Embedding.is_active.is_(True),
                Embedding.dimensions == dimensions,
            )
        )

    def _fallback_candidates(
        self,
        rows: Any,
        *,
        query_vector: list[float],
        limit: int,
        retrieval_strategy: str,
    ) -> list[Candidate]:
        ranked_rows = sorted(
            (
                (row, _cosine_distance(query_vector, list(row["vector"])))
                for row in rows
            ),
            key=lambda item: (item[1], item[0]["chunk_id"]),
        )[:limit]
        return [
            self._candidate_from_row(
                row,
                rank=index + 1,
                retrieval_strategy=retrieval_strategy,
                distance=distance,
            )
            for index, (row, distance) in enumerate(ranked_rows)
        ]

    def _candidate_from_row(
        self,
        row: RowMapping,
        *,
        rank: int,
        retrieval_strategy: str,
        distance: float | None = None,
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
        cosine_distance = row["distance"] if distance is None else distance
        return Candidate(
            chunk_id=row["chunk_id"],
            retrieval_path="vector",
            rank=rank,
            matched_fields=(),
            metadata=metadata,
            diagnostics={
                "cosine_distance": float(cosine_distance),
                "embedding_model_id": row["embedding_model_id"],
                "index_version_id": row["index_version_id"],
                "retrieval_strategy": retrieval_strategy,
            },
        )


def _query_embedding_input(
    query: RetrievalQuery,
    filters: RetrievalFilters,
    profile: VectorRetrievalProfile,
) -> EmbeddingInput:
    sanitized_query_text = sanitize_diagnostic_text(query.query_text)
    metadata = {
        "profile_id": profile.profile_id,
        "embedding_profile_id": profile.embedding_profile_id,
        "source_filter_count": str(len(filters.source_ids)),
        "version_filter_count": str(len(filters.version_labels)),
    }
    content_hash = _query_hash(sanitized_query_text, metadata)
    return EmbeddingInput(
        chunk_id=uuid5(NAMESPACE_URL, f"idp-brain:query:{content_hash}"),
        sanitized_text=sanitized_query_text,
        sanitized_content_hash=content_hash,
        metadata=metadata,
    )


def _query_hash(sanitized_query_text: str, metadata: dict[str, str]) -> str:
    hasher = hashlib.sha256()
    hasher.update(sanitized_query_text.encode())
    for key in sorted(metadata):
        hasher.update(b"\0")
        hasher.update(key.encode())
        hasher.update(b"=")
        hasher.update(metadata[key].encode())
    return f"sha256:{hasher.hexdigest()}"


def _cosine_distance(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vector dimensions do not match")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 1.0
    similarity = sum(a * b for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )
    return 1.0 - similarity


def _retrieval_strategy(
    filtered_count: int,
    profile: VectorRetrievalProfile,
) -> str:
    if filtered_count <= profile.exact_search_threshold:
        return "exact"
    return "hnsw"
