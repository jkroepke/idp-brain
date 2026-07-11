"""Typed retrieval query profile configuration."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, computed_field, model_validator

from idp_brain.config.base import ConfigModel
from idp_brain.models.relationship import RELATIONSHIP_TYPES
from idp_brain.retrieval_field_sets import BM25_RETRIEVAL_FIELDS

REQUIRED_QUERY_PROFILE_IDS = frozenset(
    {
        "docs_qa",
        "code_qa",
        "api_symbol_lookup",
        "release_change_search",
        "conflict_search",
    }
)

REQUIRED_FILTER_DIMENSIONS = frozenset(
    {
        "source_allowlist",
        "visibility",
        "sensitivity_class",
        "license_policy_status",
        "version_or_release_scope",
        "active_index_version",
    }
)

KNOWN_RETRIEVAL_FIELDS = frozenset(
    {
        "artifact_path",
        "change_summary",
        "citation_id",
        "claim_predicate",
        "claim_subject",
        "commit_sha",
        "endpoint_path",
        "error_string",
        "field_name",
        "first_seen_version",
        "flag_name",
        "function_name",
        "heading_path",
        "import_path",
        "language",
        "last_seen_version",
        "method_name",
        "release_tag",
        "sanitized_text",
        "schema_key",
        "schema_path",
        "signature_text",
        "source_id",
        "source_type",
        "symbol_path",
        "tracked_ref",
        "version_label",
    }
)

KNOWN_VECTOR_INDEX_IDS = frozenset(
    {
        "api_specs_hnsw",
        "code_chunks_hnsw",
        "conflict_claims_hnsw",
        "docs_chunks_hnsw",
        "release_notes_hnsw",
    }
)

PLACEHOLDER_RELATIONSHIP_TYPES = frozenset(
    {
        "claim_conflicts",
        "depends_on",
        "impacts",
        "version_lineage",
    }
)


class RetrievalConfigModel(ConfigModel):
    """Base model for retrieval configuration contracts."""


QueryProfileId = Literal[
    "docs_qa",
    "code_qa",
    "api_symbol_lookup",
    "release_change_search",
    "conflict_search",
]
FusionMethod = Literal["reciprocal_rank_fusion", "calibrated_weighted_fusion"]
TraversalDirection = Literal["outbound", "inbound", "both"]
TraversalCycleHandling = Literal["skip_seen", "error"]
TraversalSeedSource = Literal["exact", "bm25", "vector", "fused"]
ActiveIndexBehaviorMode = Literal["require_active", "allow_missing_for_bootstrap"]


class CandidateCountsConfig(RetrievalConfigModel):
    """Candidate limits for exact, BM25, vector, fusion, and reranking stages."""

    exact_top_k: int = Field(ge=0, le=50)
    bm25_top_k: int = Field(ge=50, le=200)
    vector_top_k: int = Field(ge=50, le=200)
    fused_top_k: int = Field(gt=0, le=200)
    rerank_top_k: int = Field(ge=0, le=200)

    @model_validator(mode="after")
    def broad_candidate_counts_are_bounded(self) -> Self:
        if self.rerank_top_k > self.fused_top_k:
            raise ValueError("rerank_top_k cannot exceed fused_top_k")
        return self


class WeightingConfig(RetrievalConfigModel):
    """Configurable ranking weight used for freshness and authority signals."""

    enabled: bool = True
    weight: float = Field(ge=0, le=1)
    strategy: str = Field(min_length=1)


class FusionWeightsConfig(RetrievalConfigModel):
    """Rank-fusion weights by candidate source."""

    exact: float = Field(default=1.0, ge=0, le=1)
    bm25: float = Field(default=1.0, ge=0, le=1)
    vector: float = Field(default=1.0, ge=0, le=1)
    relationship: float = Field(default=0.5, ge=0, le=1)
    memory: float = Field(default=0.0, ge=0, le=1)

    @model_validator(mode="after")
    def at_least_one_weight_is_positive(self) -> Self:
        if self.exact + self.bm25 + self.vector + self.relationship + self.memory <= 0:
            raise ValueError("at least one fusion weight must be greater than zero")
        return self


class RelationshipTraversalConfig(RetrievalConfigModel):
    """Bounded profile-driven relationship traversal."""

    enabled: bool = False
    relationship_types: list[str] = Field(default_factory=list)
    max_depth: int = Field(default=0, ge=0, le=3)
    max_fanout_per_seed: int = Field(default=0, ge=0, le=25)
    max_relationship_candidates: int = Field(default=0, ge=0, le=100)
    direction: TraversalDirection = "outbound"
    cycle_handling: TraversalCycleHandling = "skip_seen"
    seed_sources: list[TraversalSeedSource] = Field(default_factory=list)

    @model_validator(mode="after")
    def traversal_is_explicit_and_bounded(self) -> Self:
        known_types = set(RELATIONSHIP_TYPES) | PLACEHOLDER_RELATIONSHIP_TYPES
        unknown_types = sorted(set(self.relationship_types) - known_types)
        if unknown_types:
            allowed = ", ".join(sorted(known_types))
            invalid = ", ".join(unknown_types)
            raise ValueError(
                f"unknown relationship type(s): {invalid}; allowed or reserved: "
                f"{allowed}"
            )
        if not self.enabled:
            if self.relationship_types:
                raise ValueError(
                    "disabled relationship traversal cannot declare relationship_types"
                )
            if self.max_depth or self.max_fanout_per_seed:
                raise ValueError(
                    "disabled relationship traversal must keep depth and fanout at 0"
                )
            if self.max_relationship_candidates:
                raise ValueError(
                    "disabled relationship traversal must keep candidate count at 0"
                )
            if self.seed_sources:
                raise ValueError(
                    "disabled relationship traversal cannot declare seed_sources"
                )
            return self
        if not self.relationship_types:
            raise ValueError(
                "enabled relationship traversal requires relationship_types"
            )
        if self.max_depth < 1:
            raise ValueError("enabled relationship traversal requires max_depth >= 1")
        if self.max_fanout_per_seed < 1:
            raise ValueError(
                "enabled relationship traversal requires max_fanout_per_seed >= 1"
            )
        if self.max_relationship_candidates < 1:
            raise ValueError(
                "enabled relationship traversal requires "
                "max_relationship_candidates >= 1"
            )
        if not self.seed_sources:
            raise ValueError("enabled relationship traversal requires seed_sources")
        return self


class ActiveIndexBehaviorConfig(RetrievalConfigModel):
    """How a query profile treats active index-version scope."""

    mode: ActiveIndexBehaviorMode = "require_active"
    require_filter: bool = True

    @model_validator(mode="after")
    def active_index_filter_is_required(self) -> Self:
        if self.mode == "require_active" and not self.require_filter:
            raise ValueError(
                "active index behavior 'require_active' requires the active index "
                "filter dimension"
            )
        return self


class DiagnosticsConfig(RetrievalConfigModel):
    """Profile-level retrieval diagnostics switches."""

    enabled: bool = True
    include_candidate_counts: bool = True
    include_profile: bool = True
    include_filter_summary: bool = True
    include_relationship_traversal: bool = False
    include_scores: bool = False


class RetrievalQueryProfileConfig(RetrievalConfigModel):
    """Named query profile for generic hybrid retrieval."""

    profile_id: QueryProfileId
    exact_fields: list[str] = Field(min_length=1)
    bm25_fields: list[str] = Field(min_length=1)
    vector_index: str = Field(min_length=1)
    embedding_profile_id: str = Field(min_length=1)
    candidate_counts: CandidateCountsConfig
    fusion_method: FusionMethod = "reciprocal_rank_fusion"
    fusion_weights: FusionWeightsConfig = Field(default_factory=FusionWeightsConfig)
    reranker_profile_id: str | None = None
    relationship_traversal: RelationshipTraversalConfig = Field(
        default_factory=RelationshipTraversalConfig
    )
    filter_dimensions: list[str] = Field(min_length=1)
    active_index_behavior: ActiveIndexBehaviorConfig = Field(
        default_factory=ActiveIndexBehaviorConfig
    )
    diagnostics: DiagnosticsConfig = Field(default_factory=DiagnosticsConfig)
    freshness_weighting: WeightingConfig
    authority_weighting: WeightingConfig
    token_budget: int = Field(gt=0)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_profile_keys(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "embedding_model" in normalized:
            normalized["embedding_profile_id"] = normalized["embedding_model"]
        if "reranker" in normalized:
            normalized["reranker_profile_id"] = normalized["reranker"]
        normalized.pop("embedding_model", None)
        normalized.pop("reranker", None)
        return normalized

    @model_validator(mode="after")
    def profile_references_are_known_and_safe(self) -> Self:
        _require_known_fields(self.exact_fields, "exact_fields")
        _require_known_fields(self.bm25_fields, "bm25_fields")
        _require_bm25_indexed_fields(self.bm25_fields)
        if self.vector_index not in KNOWN_VECTOR_INDEX_IDS:
            allowed = ", ".join(sorted(KNOWN_VECTOR_INDEX_IDS))
            raise ValueError(
                f"unknown vector index {self.vector_index!r}; configure one of: "
                f"{allowed}"
            )
        missing_filters = sorted(
            REQUIRED_FILTER_DIMENSIONS - set(self.filter_dimensions)
        )
        if missing_filters:
            joined = ", ".join(missing_filters)
            raise ValueError(
                f"profile {self.profile_id!r} is missing required filter "
                f"dimension(s): {joined}"
            )
        if (
            self.active_index_behavior.require_filter
            and "active_index_version" not in self.filter_dimensions
        ):
            raise ValueError(
                f"profile {self.profile_id!r} requires active_index_version in "
                "filter_dimensions"
            )
        if (
            self.relationship_traversal.enabled
            and "active_index_version" not in self.filter_dimensions
        ):
            raise ValueError(
                f"profile {self.profile_id!r} enables relationship traversal but "
                "does not require active_index_version filtering"
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def embedding_model(self) -> str:
        """Compatibility alias for existing cross-file validation callers."""

        return self.embedding_profile_id

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reranker(self) -> str | None:
        """Compatibility alias for existing cross-file validation callers."""

        return self.reranker_profile_id


class RetrievalConfig(RetrievalConfigModel):
    """Top-level ``retrieval.yaml`` contract."""

    config_version: Literal[1]
    kind: Literal["retrieval"]
    rank_constant: int = Field(default=60, gt=0)
    query_profiles: list[RetrievalQueryProfileConfig]

    @model_validator(mode="after")
    def required_query_profiles_must_be_present_once(self) -> Self:
        configured_profiles = [profile.profile_id for profile in self.query_profiles]
        duplicates = sorted(
            {
                profile_id
                for profile_id in configured_profiles
                if configured_profiles.count(profile_id) > 1
            }
        )
        if duplicates:
            joined = ", ".join(duplicates)
            raise ValueError(f"duplicate retrieval query profiles: {joined}")
        missing_profiles = sorted(REQUIRED_QUERY_PROFILE_IDS - set(configured_profiles))
        if missing_profiles:
            joined = ", ".join(missing_profiles)
            raise ValueError(f"missing retrieval query profiles: {joined}")
        return self

    def profile_by_id(self, profile_id: QueryProfileId) -> RetrievalQueryProfileConfig:
        """Return a configured profile by ID."""

        for profile in self.query_profiles:
            if profile.profile_id == profile_id:
                return profile
        raise KeyError(profile_id)


def _require_known_fields(fields: list[str], field_group: str) -> None:
    unknown_fields = sorted(set(fields) - KNOWN_RETRIEVAL_FIELDS)
    if unknown_fields:
        allowed = ", ".join(sorted(KNOWN_RETRIEVAL_FIELDS))
        invalid = ", ".join(unknown_fields)
        raise ValueError(
            f"unknown retrieval field(s) in {field_group}: {invalid}; allowed or "
            f"reserved fields: {allowed}"
        )


def _require_bm25_indexed_fields(fields: list[str]) -> None:
    unsupported_fields = sorted(set(fields) - set(BM25_RETRIEVAL_FIELDS))
    if unsupported_fields:
        allowed = ", ".join(BM25_RETRIEVAL_FIELDS)
        invalid = ", ".join(unsupported_fields)
        raise ValueError(
            f"BM25 field(s) are not backed by the chunks BM25 index: {invalid}; "
            f"indexed fields: {allowed}"
        )
