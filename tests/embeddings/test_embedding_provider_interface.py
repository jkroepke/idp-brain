from __future__ import annotations

from uuid import uuid4

import pytest

from idp_brain.config import load_config_dir
from idp_brain.config.models import EmbeddingProfileConfig
from idp_brain.embeddings import (
    DeterministicMockEmbeddingProvider,
    EmbeddingInput,
    EmbeddingProviderConfigError,
    EmbeddingProviderRegistry,
)


def test_provider_interface_accepts_only_sanitized_text_field() -> None:
    fields = set(EmbeddingInput.__dataclass_fields__)

    assert fields == {
        "chunk_id",
        "sanitized_text",
        "sanitized_content_hash",
        "metadata",
    }
    assert "raw_text" not in fields
    assert "raw_chunk_text" not in fields
    assert "debug_payload" not in fields


def test_registry_resolves_mock_provider_from_profile_id() -> None:
    profile = EmbeddingProfileConfig(
        profile_id="docs_default",
        provider_id="mock",
        model_name="deterministic-docs-default-v1",
        dimensions=8,
        deterministic=True,
    )
    provider = EmbeddingProviderRegistry([profile]).resolve("docs_default")

    assert isinstance(provider, DeterministicMockEmbeddingProvider)
    assert provider.provider_id == "mock"
    assert provider.model_id == "deterministic-docs-default-v1"
    assert provider.dimensions == 8


def test_registry_rejects_unknown_and_disabled_profiles() -> None:
    disabled = EmbeddingProfileConfig(
        profile_id="disabled",
        provider_id="mock",
        model_name="mock-v1",
        enabled=False,
        dimensions=8,
    )
    registry = EmbeddingProviderRegistry([disabled])

    with pytest.raises(EmbeddingProviderConfigError, match="unknown"):
        registry.resolve("missing")
    with pytest.raises(EmbeddingProviderConfigError, match="disabled"):
        registry.resolve("disabled")


def test_external_provider_requires_explicit_environment_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    external = EmbeddingProfileConfig.model_construct(
        profile_id="external-docs",
        provider_id="openai",
        model_name="text-embedding-3-small",
        enabled=True,
        external=True,
        deterministic=False,
        dimensions=1536,
        batch_size=16,
        timeout_seconds=30,
        required_env_vars=["OPENAI_API_KEY"],
        token_limit=8191,
        options={},
    )

    monkeypatch.delenv("IDP_BRAIN_ALLOW_EXTERNAL_MODELS", raising=False)
    with pytest.raises(EmbeddingProviderConfigError, match="requires"):
        EmbeddingProviderRegistry([external]).resolve("external-docs")

    monkeypatch.setenv("IDP_BRAIN_ALLOW_EXTERNAL_MODELS", "false")
    with pytest.raises(EmbeddingProviderConfigError, match="requires"):
        EmbeddingProviderRegistry([external]).resolve("external-docs")

    monkeypatch.setenv("IDP_BRAIN_ALLOW_EXTERNAL_MODELS", "true")
    provider = EmbeddingProviderRegistry([external]).resolve("external-docs")
    with pytest.raises(EmbeddingProviderConfigError, match="OPENAI_API_KEY"):
        provider.embed(
            [
                EmbeddingInput(
                    chunk_id=uuid4(),
                    sanitized_text="safe text",
                    sanitized_content_hash="sha256:safe",
                    metadata={},
                )
            ]
        )


def test_example_models_config_contains_required_mvp_profiles() -> None:
    bundle = load_config_dir(__import__("pathlib").Path("config"))
    profiles = {
        profile.profile_id: profile for profile in bundle.models.embedding_profiles
    }

    assert {"docs_default", "docs_quality", "code_default", "memory_default"} <= set(
        profiles
    )
    for profile_id in [
        "docs_default",
        "docs_quality",
        "code_default",
        "memory_default",
    ]:
        profile = profiles[profile_id]
        assert profile.provider_id == "mock"
        assert profile.deterministic is True
        assert profile.external is False
        assert profile.dimensions > 0
        assert profile.batch_size > 0
        assert profile.timeout_seconds > 0
        assert profile.required_env_vars == []
