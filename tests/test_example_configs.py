from __future__ import annotations

from pathlib import Path

import pytest

from idp_brain.config import ConfigBundle, load_config_dir
from idp_brain.models.policy import LICENSE_POLICY_STATUSES, VISIBILITY_LABELS

EXPECTED_QUERY_PROFILES = {
    "docs_qa",
    "code_qa",
    "api_symbol_lookup",
    "release_change_search",
    "conflict_search",
}
EXPECTED_MEMORY_SCOPES = {"session", "project", "user", "system"}
LOCAL_DETERMINISTIC_PROVIDERS = {"local", "local_mock", "mock"}
REMOTE_PROVIDERS = {
    "openai",
    "jina",
    "cohere",
    "litellm",
    "vllm",
    "bentoml",
    "kserve",
}


@pytest.fixture
def bundle() -> ConfigBundle:
    return load_config_dir(Path("config"))


def test_example_config_dir_loads(bundle: ConfigBundle) -> None:
    assert bundle.sources.kind == "sources"
    assert bundle.extractors.kind == "extractors"
    assert bundle.models.kind == "models"
    assert bundle.retrieval.kind == "retrieval"
    assert bundle.evaluation.kind == "evaluation"
    assert bundle.security.kind == "security"
    assert bundle.access.kind == "access"
    assert bundle.memory.kind == "memory"


def test_active_model_profiles_are_deterministic_local_or_mock(
    bundle: ConfigBundle,
) -> None:
    active_embeddings = [
        profile for profile in bundle.models.embedding_profiles if profile.enabled
    ]
    active_rerankers = [
        profile for profile in bundle.models.reranker_profiles if profile.enabled
    ]

    assert active_embeddings
    assert active_rerankers
    for profile in [*active_embeddings, *active_rerankers]:
        assert profile.provider in LOCAL_DETERMINISTIC_PROVIDERS
        assert profile.deterministic is True
        assert profile.external is False


def test_disabled_external_examples_are_not_enabled(bundle: ConfigBundle) -> None:
    all_profiles = [
        *bundle.models.embedding_profiles,
        *bundle.models.reranker_profiles,
        *bundle.models.generator_profiles,
    ]
    external_profiles = [profile for profile in all_profiles if profile.external]
    enabled_remote_profiles = [
        profile
        for profile in all_profiles
        if profile.enabled and profile.provider in REMOTE_PROVIDERS
    ]

    assert external_profiles
    assert all(profile.enabled is False for profile in external_profiles)
    assert enabled_remote_profiles == []
    assert bundle.models.budgets.max_external_requests_per_run == 0


def test_source_access_labels_and_policies_are_present(
    bundle: ConfigBundle,
) -> None:
    source_ids = {source.source_id for source in bundle.sources.sources}
    allowlisted_source_ids = set(bundle.security.source_allowlist.source_ids)
    visibility_labels = {label.label for label in bundle.access.visibility_labels}
    sensitivity_labels = {label.label for label in bundle.access.sensitivity_labels}
    license_labels = {label.label for label in bundle.access.license_policy_labels}

    assert {"local-docs", "local-source-tree", "local-config-examples"} <= source_ids
    assert allowlisted_source_ids <= source_ids
    assert {"public", "internal", "restricted"} <= visibility_labels
    assert {"public", "internal", "confidential", "restricted"} <= sensitivity_labels
    assert {"allowed", "review_required", "restricted", "unknown"} <= license_labels
    assert bundle.access.default_deny is True
    assert bundle.access.unknown_label_policy == "deny"
    assert bundle.access.acl_policies
    assert all(policy.default_deny is True for policy in bundle.access.acl_policies)

    for source in bundle.sources.sources:
        assert source.tracked_refs
        assert source.local_path or source.url
        assert source.include_paths
        assert source.exclude_paths
        assert source.allowed_groups or source.allowed_principals
        assert source.corpus_eligibility
        assert source.visibility_label in visibility_labels
        assert source.sensitivity_class in sensitivity_labels
        assert source.license_policy in license_labels


def test_example_local_directory_sources_use_schema_safe_policy_labels(
    bundle: ConfigBundle,
) -> None:
    local_directory_sources = [
        source
        for source in bundle.sources.sources
        if source.source_type == "local_directory"
    ]

    assert local_directory_sources
    for source in local_directory_sources:
        assert source.visibility_label in VISIBILITY_LABELS
        assert source.license_policy in LICENSE_POLICY_STATUSES
        assert source.license_policy != "allowed"


def test_required_retrieval_query_profiles_are_configured(
    bundle: ConfigBundle,
) -> None:
    query_profiles = {profile.profile_id for profile in bundle.retrieval.query_profiles}

    assert query_profiles == EXPECTED_QUERY_PROFILES
    for profile in bundle.retrieval.query_profiles:
        assert profile.exact_fields
        assert profile.bm25_fields
        assert profile.vector_index
        assert profile.embedding_model
        assert profile.reranker
        assert profile.candidate_counts.fused_top_k > 0
        assert profile.freshness_weighting.strategy
        assert profile.authority_weighting.strategy
        assert profile.token_budget > 0


def test_evaluation_is_diagnostic_only(bundle: ConfigBundle) -> None:
    assert bundle.evaluation.mode == "diagnostic"
    assert bundle.evaluation.fixtures
    assert bundle.evaluation.thresholds
    for fixture in bundle.evaluation.fixtures:
        fixture_path = Path(fixture.path)
        assert not fixture_path.is_absolute()
        assert fixture_path.is_file()
    assert all(
        threshold.release_blocking is False
        for threshold in bundle.evaluation.thresholds
    )
    assert bundle.evaluation.embedding_fine_tuning.enabled is False


def test_memory_retrieval_influence_is_disabled(bundle: ConfigBundle) -> None:
    memory_scopes = {scope.scope for scope in bundle.memory.scopes}
    promotion_types = {rule.memory_type for rule in bundle.memory.promotion_rules}

    assert memory_scopes == EXPECTED_MEMORY_SCOPES
    assert promotion_types == {
        "preference",
        "decision",
        "correction",
        "retrieval_feedback",
        "evaluation_observation",
        "source_policy",
        "workflow_note",
    }
    assert bundle.memory.retrieval_influence.enabled is False
    assert bundle.memory.retrieval_influence.allowed_scopes == []
    assert bundle.memory.retrieval_influence.max_boost == 0
    assert bundle.memory.retrieval_influence.token_budget == 0
