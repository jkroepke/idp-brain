"""Shared retrieval request and candidate records."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RetrievalPath = Literal["exact", "fuzzy", "bm25"]
BM25_RETRIEVAL_FIELDS = (
    "sanitized_text",
    "heading_path",
    "symbol_path",
    "signature_text",
    "artifact_path",
)
DEFAULT_RETRIEVAL_SENSITIVITY_CLASSES = ("public", "internal", "confidential")
DEFAULT_RETRIEVAL_LICENSE_POLICY_STATUSES = ("allowed",)
DEFAULT_RETRIEVAL_CORPUS_ELIGIBILITY_LABELS = (
    "allowed",
    "default_retrievable",
    "eligible",
    "review_required",
)


class RetrievalQuery(BaseModel):
    """User query text and exact-lookup options."""

    model_config = ConfigDict(frozen=True)

    query_text: str = Field(min_length=1)
    enable_fuzzy: bool = False


class RetrievalFilters(BaseModel):
    """Trusted filters applied before lookup predicates."""

    model_config = ConfigDict(frozen=True)

    source_ids: tuple[str, ...] = ()
    source_types: tuple[str, ...] = ()
    version_labels: tuple[str, ...] = ()
    visibility_labels: tuple[str, ...] = ()
    sensitivity_classes: tuple[str, ...] = DEFAULT_RETRIEVAL_SENSITIVITY_CLASSES
    license_policy_statuses: tuple[str, ...] = DEFAULT_RETRIEVAL_LICENSE_POLICY_STATUSES
    license_ids: tuple[str, ...] = ()
    redaction_statuses: tuple[str, ...] = ("redacted", "not_required")
    corpus_eligibility_labels: tuple[str, ...] = (
        DEFAULT_RETRIEVAL_CORPUS_ELIGIBILITY_LABELS
    )
    active_index_version_id: str | None = None


class BM25RetrievalProfile(BaseModel):
    """Temporary BM25 settings until query profiles are formalized."""

    model_config = ConfigDict(frozen=True)

    profile_id: str = "bm25_default"
    bm25_fields: tuple[str, ...] = BM25_RETRIEVAL_FIELDS
    candidate_limit: int = Field(default=20, gt=0, le=200)

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


class Candidate(BaseModel):
    """A sanitized retrieval candidate ready for later fusion."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    retrieval_path: RetrievalPath
    rank: int
    matched_fields: tuple[str, ...]
    metadata: dict[str, Any]
    diagnostics: dict[str, Any] = Field(default_factory=dict)
