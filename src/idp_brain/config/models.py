"""Typed configuration models for versioned idp-brain YAML files."""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import Field, model_validator

from idp_brain.config.base import ConfigModel
from idp_brain.config.retrieval import RetrievalConfig

ScalarValue = str | int | float | bool | None


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
    include_generated: bool = False
    include_vendored: bool = False
    discovery_override_reason: str | None = None
    override_exclude_paths: list[str] = Field(default_factory=list)
    source_priority: int = Field(ge=0)
    visibility_label: str = Field(min_length=1)
    corpus_eligibility: str = Field(min_length=1)
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


class EmbeddingProfileConfig(ConfigModel):
    """Embedding provider profile for sanitized chunk vectors."""

    profile_id: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    enabled: bool = True
    external: bool = False
    deterministic: bool = False
    dimensions: int = Field(gt=0)
    batch_size: int = Field(default=32, gt=0)
    timeout_seconds: float = Field(default=30, gt=0)
    required_env_vars: list[str] = Field(default_factory=list)
    token_limit: int | None = Field(default=None, gt=0)
    options: dict[str, ScalarValue] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_model_profile_keys(cls, data: Any) -> Any:
        """Allow older model profile keys while exposing the 4.1 contract."""

        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "profile_id" not in normalized and "model_id" in normalized:
            normalized["profile_id"] = normalized["model_id"]
        if "provider_id" not in normalized and "provider" in normalized:
            normalized["provider_id"] = normalized["provider"]
        if "model_name" not in normalized and "provider_model_id" in normalized:
            normalized["model_name"] = normalized["provider_model_id"]
        normalized.pop("model_id", None)
        normalized.pop("provider", None)
        normalized.pop("provider_model_id", None)
        return normalized

    @model_validator(mode="after")
    def external_profiles_must_be_disabled(self) -> Self:
        """Prevent accidental external model calls from config alone."""

        if self.external and self.enabled:
            raise ValueError(
                "external embedding profiles must set enabled=false until settings "
                "explicitly allow external calls"
            )
        return self

    @property
    def model_id(self) -> str:
        """Compatibility alias used by existing retrieval config references."""

        return self.profile_id

    @property
    def provider(self) -> str:
        """Compatibility alias for existing model-profile callers."""

        return self.provider_id

    @property
    def provider_model_id(self) -> str:
        """Compatibility alias for existing model-profile callers."""

        return self.model_name


class RerankerProfileConfig(ConfigModel):
    """Safe runtime settings for one reranking provider."""

    profile_id: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    enabled: bool = True
    external: bool = False
    deterministic: bool = False
    candidate_limit: int = Field(default=50, gt=0, le=200)
    timeout_seconds: float = Field(default=10, gt=0)
    max_text_length: int = Field(default=4096, gt=0)
    required_env_vars: list[str] = Field(default_factory=list)
    allow_fallback: bool = False
    required: bool = True
    options: dict[str, ScalarValue] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        value = dict(data)
        value["profile_id"] = value.pop("model_id", value.get("profile_id"))
        value["provider_id"] = value.pop("provider", value.get("provider_id"))
        value["model_name"] = value.pop("provider_model_id", value.get("model_name"))
        token_limit = value.pop("token_limit", None)
        value.pop("dimensions", None)
        if token_limit and "max_text_length" not in value:
            value["max_text_length"] = token_limit
        return value

    @property
    def model_id(self) -> str:
        return self.profile_id

    @property
    def provider(self) -> str:
        """Compatibility alias for existing generic model-profile callers."""

        return self.provider_id

    @property
    def provider_model_id(self) -> str:
        """Compatibility alias for existing generic model-profile callers."""

        return self.model_name


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
    embedding_profiles: list[EmbeddingProfileConfig]
    reranker_profiles: list[RerankerProfileConfig]
    generator_profiles: list[ModelProfileConfig] = Field(default_factory=list)
    provider_routes: list[ProviderRouteConfig] = Field(default_factory=list)
    budgets: ModelBudgetsConfig


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
