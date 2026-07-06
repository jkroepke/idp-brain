"""Typed configuration models for versioned idp-brain YAML files."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

ScalarValue = str | int | float | bool | None


class ConfigModel(BaseModel):
    """Base model for all configuration contracts."""

    model_config = ConfigDict(extra="forbid")


SourceType = Literal[
    "git_repository",
    "git_repository_digest",
    "release_artifact",
    "documentation_site",
    "documentation_file",
    "openapi_spec",
    "schema_bundle",
    "local_directory",
]

VersionStrategy = Literal[
    "tags",
    "releases",
    "branches",
    "semver",
    "calendar_versions",
    "explicit_refs",
    "digest",
    "snapshot",
]


class SourceConfig(ConfigModel):
    """One configured source catalog entry."""

    source_id: str = Field(min_length=1)
    source_type: SourceType
    url: str | None = None
    local_path: str | None = None
    tracked_refs: list[str] = Field(default_factory=list)
    version_strategy: VersionStrategy
    include_paths: list[str] = Field(default_factory=list)
    exclude_paths: list[str] = Field(default_factory=list)
    extractor_profile: str = Field(min_length=1)
    source_priority: int = Field(ge=0)
    visibility_label: str = Field(min_length=1)
    allowed_groups: list[str] = Field(default_factory=list)
    allowed_principals: list[str] = Field(default_factory=list)
    sensitivity_class: str = Field(min_length=1)
    license_policy: str = Field(min_length=1)
    refresh_cadence: str = Field(min_length=1)
    enabled: bool = True


class SourcesConfig(ConfigModel):
    """Top-level ``sources.yaml`` contract."""

    config_version: Literal[1]
    kind: Literal["sources"]
    sources: list[SourceConfig]


ExtractorFamily = Literal[
    "code",
    "docs",
    "schemas",
    "api_specs",
    "repository_digest",
    "security_scanner",
    "validator",
]


class ExtractorToolConfig(ConfigModel):
    """Generic extractor tool configuration without a hardcoded tool catalog."""

    tool_id: str = Field(min_length=1)
    enabled: bool = True
    command: list[str] = Field(default_factory=list)
    options: dict[str, ScalarValue] = Field(default_factory=dict)


class ValidatorCommandConfig(ConfigModel):
    """Configured validation command for a profile."""

    command_id: str = Field(min_length=1)
    command: list[str] = Field(min_length=1)
    enabled: bool = True
    timeout_seconds: int = Field(default=60, ge=1)


class ExtractorProfileConfig(ConfigModel):
    """Extractor profile for code, docs, schemas, API specs, and fallbacks."""

    profile_id: str = Field(min_length=1)
    family: ExtractorFamily
    enabled: bool = True
    file_patterns: list[str] = Field(default_factory=list)
    include_generated: bool = False
    include_vendored: bool = False
    tools: list[ExtractorToolConfig] = Field(default_factory=list)
    validator_commands: list[ValidatorCommandConfig] = Field(default_factory=list)
    fallback_profile: str | None = None


class ExtractorsConfig(ConfigModel):
    """Top-level ``extractors.yaml`` contract."""

    config_version: Literal[1]
    kind: Literal["extractors"]
    profiles: list[ExtractorProfileConfig]


ModelPurpose = Literal["embedding", "reranker", "generator"]


class ModelProfileConfig(ConfigModel):
    """Model profile for embeddings, reranking, or generation."""

    model_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    provider_model_id: str = Field(min_length=1)
    enabled: bool = True
    external: bool = False
    deterministic: bool = False
    dimensions: int | None = Field(default=None, gt=0)
    token_limit: int | None = Field(default=None, gt=0)
    options: dict[str, ScalarValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def external_profiles_must_be_disabled(self) -> Self:
        """Prevent accidental external model calls from config alone."""

        if self.external and self.enabled:
            raise ValueError(
                "external model profiles must set enabled=false until settings "
                "explicitly allow external calls"
            )
        return self


class ProviderRouteConfig(ConfigModel):
    """Provider routing for one model purpose."""

    route_id: str = Field(min_length=1)
    purpose: ModelPurpose
    primary_model: str = Field(min_length=1)
    fallback_models: list[str] = Field(default_factory=list)
    enabled: bool = True


class ModelBudgetsConfig(ConfigModel):
    """Model-call and token budgets enforced by later runtime phases."""

    max_embedding_tokens_per_item: int = Field(gt=0)
    max_rerank_candidates: int = Field(ge=0)
    max_generator_context_tokens: int = Field(ge=0)
    max_external_requests_per_run: int = Field(default=0, ge=0)


class ModelsConfig(ConfigModel):
    """Top-level ``models.yaml`` contract."""

    config_version: Literal[1]
    kind: Literal["models"]
    embedding_profiles: list[ModelProfileConfig]
    reranker_profiles: list[ModelProfileConfig]
    generator_profiles: list[ModelProfileConfig] = Field(default_factory=list)
    provider_routes: list[ProviderRouteConfig] = Field(default_factory=list)
    budgets: ModelBudgetsConfig


QueryProfileId = Literal[
    "docs_qa",
    "code_qa",
    "api_symbol_lookup",
    "release_change_search",
    "conflict_search",
]

FusionMethod = Literal["reciprocal_rank_fusion", "weighted_sum", "rrf"]


class CandidateCountsConfig(ConfigModel):
    """Candidate limits for exact, BM25, vector, fusion, and reranking stages."""

    exact_top_k: int = Field(ge=0)
    bm25_top_k: int = Field(ge=0)
    vector_top_k: int = Field(ge=0)
    fused_top_k: int = Field(gt=0)
    rerank_top_k: int = Field(ge=0)


class WeightingConfig(ConfigModel):
    """Configurable ranking weight used for freshness and authority signals."""

    enabled: bool = True
    weight: float = Field(ge=0)
    strategy: str = Field(min_length=1)


class RetrievalQueryProfileConfig(ConfigModel):
    """Named query profile for hybrid retrieval."""

    profile_id: QueryProfileId
    exact_fields: list[str] = Field(min_length=1)
    bm25_fields: list[str] = Field(min_length=1)
    vector_index: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    candidate_counts: CandidateCountsConfig
    fusion_method: FusionMethod
    reranker: str | None = None
    freshness_weighting: WeightingConfig
    authority_weighting: WeightingConfig
    token_budget: int = Field(gt=0)


class RetrievalConfig(ConfigModel):
    """Top-level ``retrieval.yaml`` contract."""

    config_version: Literal[1]
    kind: Literal["retrieval"]
    query_profiles: list[RetrievalQueryProfileConfig]

    @model_validator(mode="after")
    def required_query_profiles_must_be_present(self) -> Self:
        required_profiles = {
            "docs_qa",
            "code_qa",
            "api_symbol_lookup",
            "release_change_search",
            "conflict_search",
        }
        configured_profiles = {profile.profile_id for profile in self.query_profiles}
        missing_profiles = sorted(required_profiles - configured_profiles)
        if missing_profiles:
            joined = ", ".join(missing_profiles)
            raise ValueError(f"missing retrieval query profiles: {joined}")
        return self


class EvaluationFixtureConfig(ConfigModel):
    """Local deterministic retrieval evaluation fixture metadata."""

    fixture_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    enabled: bool = True


class EvaluationThresholdConfig(ConfigModel):
    """Diagnostic or release-gating metric threshold."""

    metric_id: str = Field(min_length=1)
    minimum: float = Field(ge=0)
    release_blocking: bool = False


class EmbeddingFineTuningConfig(ConfigModel):
    """Future embedding fine-tuning config, intentionally disabled in the MVP."""

    enabled: Literal[False] = False
    candidate_models: list[str] = Field(default_factory=list)
    training_dataset: str | None = None


class EvaluationConfig(ConfigModel):
    """Top-level ``evaluation.yaml`` contract."""

    config_version: Literal[1]
    kind: Literal["evaluation"]
    mode: Literal["diagnostic", "gated"] = "diagnostic"
    fixtures: list[EvaluationFixtureConfig] = Field(default_factory=list)
    thresholds: list[EvaluationThresholdConfig] = Field(default_factory=list)
    embedding_fine_tuning: EmbeddingFineTuningConfig

    @model_validator(mode="after")
    def gated_mode_requires_thresholds(self) -> Self:
        if self.mode == "gated" and not self.thresholds:
            raise ValueError("evaluation mode 'gated' requires explicit thresholds")
        return self


class SourceAllowlistConfig(ConfigModel):
    """Source allowlist defaults for later pre-subquery filtering."""

    mode: Literal["deny_all", "explicit", "all_configured"]
    source_ids: list[str] = Field(default_factory=list)


RedactionSeverity = Literal["low", "medium", "high", "critical"]


class RedactionRuleConfig(ConfigModel):
    """Configured redaction marker rule without storing matched values."""

    rule_id: str = Field(min_length=1)
    marker: str = Field(min_length=1)
    detector: str = Field(min_length=1)
    enabled: bool = True
    severity: RedactionSeverity
    pattern: str | None = None


class PiiProfileConfig(ConfigModel):
    """PII profile placeholder for later scanner integration."""

    profile_id: str = Field(min_length=1)
    enabled: bool = False
    detectors: list[str] = Field(default_factory=list)


class PromptInjectionConfig(ConfigModel):
    """Prompt-injection handling policy for source text."""

    enabled: bool = True
    action: Literal["reject", "strip", "annotate", "quarantine"]
    source_text_is_instruction: Literal[False] = False


class SecurityConfig(ConfigModel):
    """Top-level ``security.yaml`` contract."""

    config_version: Literal[1]
    kind: Literal["security"]
    source_allowlist: SourceAllowlistConfig
    redaction_rules: list[RedactionRuleConfig] = Field(default_factory=list)
    pii_profiles: list[PiiProfileConfig] = Field(default_factory=list)
    prompt_injection: PromptInjectionConfig


class LabelConfig(ConfigModel):
    """Configured visibility, sensitivity, or license policy label."""

    label: str = Field(min_length=1)
    description: str | None = None
    rank: int = Field(default=0, ge=0)


class AclPolicyConfig(ConfigModel):
    """Access-control policy metadata for later retrieval filtering."""

    policy_id: str = Field(min_length=1)
    visibility_label: str | None = None
    allowed_groups: list[str] = Field(default_factory=list)
    allowed_principals: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    source_filters: dict[str, ScalarValue] = Field(default_factory=dict)
    chunk_filters: dict[str, ScalarValue] = Field(default_factory=dict)
    default_deny: bool = True


class AccessConfig(ConfigModel):
    """Top-level ``access.yaml`` contract."""

    config_version: Literal[1]
    kind: Literal["access"]
    visibility_labels: list[LabelConfig]
    sensitivity_labels: list[LabelConfig]
    license_policy_labels: list[LabelConfig]
    acl_policies: list[AclPolicyConfig] = Field(default_factory=list)
    default_deny: bool = True
    unknown_label_policy: Literal["deny"] = "deny"


MemoryScope = Literal["session", "project", "user", "system"]
MemoryItemType = Literal[
    "preference",
    "decision",
    "correction",
    "retrieval_feedback",
    "evaluation_observation",
    "source_policy",
    "workflow_note",
]


class MemoryScopeConfig(ConfigModel):
    """Memory scope metadata; memory UX is outside the MVP."""

    scope: MemoryScope
    enabled: bool = True
    visibility_label: str = Field(min_length=1)
    sensitivity_class: str = Field(min_length=1)
    retention_policy: str = Field(min_length=1)


class MemoryRetentionConfig(ConfigModel):
    """Retention policy for memory records."""

    policy_id: str = Field(min_length=1)
    ttl_days: int | None = Field(default=None, gt=0)
    max_items: int = Field(gt=0)
    redact_before_storage: bool = True


class MemoryPromotionRuleConfig(ConfigModel):
    """Promotion rule for explicitly accepted memory writes."""

    rule_id: str = Field(min_length=1)
    memory_type: MemoryItemType
    requires_operator_approval: bool = True
    required_citations: bool = True
    min_confidence: float = Field(ge=0, le=1)


class MemoryRetrievalInfluenceConfig(ConfigModel):
    """Limits for memory influence on retrieval."""

    enabled: bool = False
    allowed_scopes: list[MemoryScope] = Field(default_factory=list)
    max_boost: float = Field(default=0, ge=0)
    token_budget: int = Field(default=0, ge=0)


class MemoryConfig(ConfigModel):
    """Top-level ``memory.yaml`` contract."""

    config_version: Literal[1]
    kind: Literal["memory"]
    scopes: list[MemoryScopeConfig]
    retention_policies: list[MemoryRetentionConfig]
    promotion_rules: list[MemoryPromotionRuleConfig]
    retrieval_influence: MemoryRetrievalInfluenceConfig


class ConfigBundle(ConfigModel):
    """Fully validated configuration bundle."""

    sources: SourcesConfig
    extractors: ExtractorsConfig
    models: ModelsConfig
    retrieval: RetrievalConfig
    evaluation: EvaluationConfig
    security: SecurityConfig
    access: AccessConfig
    memory: MemoryConfig
