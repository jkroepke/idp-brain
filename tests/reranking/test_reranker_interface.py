from __future__ import annotations

from dataclasses import fields

import pytest

from idp_brain.config.models import RerankerProfileConfig
from idp_brain.reranking.providers import (
    RerankerCandidate,
    RerankerRegistry,
    RerankerUnavailableError,
)


def profile(**updates: object) -> RerankerProfileConfig:
    return RerankerProfileConfig(
        profile_id="p", provider_id="mock", model_name="m", **updates
    )


def test_provider_input_contract_contains_only_sanitized_boundary_fields() -> None:
    assert {field.name for field in fields(RerankerCandidate)} == {
        "chunk_id",
        "sanitized_text",
        "sanitized_metadata",
        "fused_rank",
        "authority_rank",
        "freshness",
    }


def test_external_registry_requires_permission_and_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = RerankerRegistry(
        [profile(external=True, required_env_vars=["RERANK_KEY"])]
    )
    registry.register("mock", object())  # type: ignore[arg-type]
    with pytest.raises(RerankerUnavailableError):
        registry.resolve("p")
    monkeypatch.setenv("IDP_BRAIN_ALLOW_EXTERNAL_MODELS", "true")
    with pytest.raises(RerankerUnavailableError):
        registry.resolve("p")
    monkeypatch.setenv("RERANK_KEY", "secret")
    assert registry.resolve("p")[0].profile_id == "p"


def test_disabled_profile_fails_closed() -> None:
    registry = RerankerRegistry([profile(enabled=False)])
    with pytest.raises(RerankerUnavailableError, match="unavailable"):
        registry.resolve("p")
