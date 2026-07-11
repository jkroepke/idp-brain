"""Shared retrieval request and candidate records."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from idp_brain.retrieval_field_sets import BM25_RETRIEVAL_FIELDS

RetrievalPath = Literal["exact", "fuzzy", "bm25", "vector", "relationship", "memory"]
DEFAULT_RETRIEVAL_SENSITIVITY_CLASSES = ("public",)
DEFAULT_RETRIEVAL_LICENSE_POLICY_STATUSES = ("allowed",)
DEFAULT_RETRIEVAL_CORPUS_ELIGIBILITY_LABELS = (
    "allowed",
    "default_retrievable",
    "eligible",
)


class RetrievalQuery(BaseModel):
    """User query text and exact-lookup options."""

    model_config = ConfigDict(frozen=True)

    query_text: str = Field(min_length=1)
    enable_fuzzy: bool = False


class RetrievalFilterSet(BaseModel):
    """Request filters applied before lookup predicates.

    Version and release bounds compare opaque stored labels lexicographically; they
    are not semantic-version ranges. Callers needing semantic ordering must resolve
    labels to an explicit set before constructing this model.
    """

    model_config = ConfigDict(frozen=True)

    source_ids: tuple[str, ...] = ()
    source_types: tuple[str, ...] = ()
    version_labels: tuple[str, ...] = ()
    version_from: str | None = None
    version_to: str | None = None
    release_from: str | None = None
    release_to: str | None = None
    time_from: datetime | None = None
    time_to: datetime | None = None
    source_allowlisted: bool = True
    visibility_labels: tuple[str, ...] = ("invited_users",)
    sensitivity_classes: tuple[str, ...] = DEFAULT_RETRIEVAL_SENSITIVITY_CLASSES
    license_policy_statuses: tuple[str, ...] = DEFAULT_RETRIEVAL_LICENSE_POLICY_STATUSES
    license_ids: tuple[str, ...] = ("MIT", "Apache-2.0")
    redaction_statuses: tuple[str, ...] = ("redacted", "not_required")
    corpus_eligibility_labels: tuple[str, ...] = (
        DEFAULT_RETRIEVAL_CORPUS_ELIGIBILITY_LABELS
    )
    active_index_version_id: str | None = None


# Compatibility name retained for the 4.5--4.7 public API.
RetrievalFilters = RetrievalFilterSet


class BM25RetrievalProfile(BaseModel):
    """Temporary BM25 settings until query profiles are formalized."""

    model_config = ConfigDict(frozen=True)

    profile_id: str = "bm25_default"
    bm25_fields: tuple[str, ...] = Field(
        default=BM25_RETRIEVAL_FIELDS,
        min_length=1,
    )
    candidate_limit: int = Field(default=50, ge=50, le=200)
    require_active_index: bool = False

    @field_validator("bm25_fields")
    @classmethod
    def _validate_bm25_fields(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        invalid_fields = tuple(
            field for field in value if field not in BM25_RETRIEVAL_FIELDS
        )
        if invalid_fields:
            allowed = ", ".join(BM25_RETRIEVAL_FIELDS)
            invalid = ", ".join(invalid_fields)
            raise ValueError(
                f"Unsupported BM25 field(s): {invalid}; allowed: {allowed}"
            )
        return value


class VectorRetrievalProfile(BaseModel):
    """Vector retrieval settings resolved from the active query profile."""

    model_config = ConfigDict(frozen=True)

    profile_id: str = "vector_default"
    embedding_profile_id: str = Field(default="docs_default", min_length=1)
    embedding_model_id: str = Field(min_length=1)
    index_version_id: str = Field(min_length=1)
    candidate_limit: int = Field(default=50, ge=50, le=200)
    require_active_index: bool = False
    hnsw_ef_search: int = Field(default=100, gt=0)
    exact_search_threshold: int = Field(default=200, ge=0)


class Candidate(BaseModel):
    """A sanitized retrieval candidate ready for later fusion."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    retrieval_path: RetrievalPath
    rank: int
    matched_fields: tuple[str, ...]
    metadata: dict[str, Any]
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    sanitized_excerpt: str | None = None
    sanitized_excerpt_trusted: bool = False


class FusedCandidate(BaseModel):
    """Deduplicated candidate with path-local diagnostics and an RRF score."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    fused_score: float
    path_candidates: dict[str, Candidate]
    metadata: dict[str, Any] = Field(default_factory=dict)
    fused_rank: int | None = None
    reranked_rank: int | None = None
    rerank_score: float | None = None
    rerank_diagnostics: dict[str, Any] = Field(default_factory=dict)
    sanitized_excerpt: str | None = None
    sanitized_excerpt_trusted: bool = False

    @property
    def retrieval_paths(self) -> tuple[str, ...]:
        return tuple(sorted(self.path_candidates))
