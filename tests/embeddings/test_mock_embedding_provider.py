from __future__ import annotations

import logging
from uuid import uuid4

from idp_brain.config.models import EmbeddingProfileConfig
from idp_brain.embeddings import (
    DeterministicMockEmbeddingProvider,
    EmbeddingInput,
)


def _profile(
    *,
    profile_id: str = "docs_default",
    model_name: str = "mock-v1",
    dimensions: int = 8,
) -> EmbeddingProfileConfig:
    return EmbeddingProfileConfig(
        profile_id=profile_id,
        provider_id="mock",
        model_name=model_name,
        deterministic=True,
        dimensions=dimensions,
        batch_size=4,
        timeout_seconds=5,
    )


def _input(content_hash: str = "sha256:abc") -> EmbeddingInput:
    return EmbeddingInput(
        chunk_id=uuid4(),
        sanitized_text="sanitized content only",
        sanitized_content_hash=content_hash,
        metadata={"source_id": "fixture"},
    )


def test_identical_sanitized_hashes_produce_identical_vectors() -> None:
    provider = DeterministicMockEmbeddingProvider(_profile())
    first = provider.embed([_input("sha256:same")])[0]
    second = provider.embed([_input("sha256:same")])[0]

    assert first.values == second.values
    assert first.dimensions == 8
    assert len(first.values) == 8
    assert all(-1.0 <= value <= 1.0 for value in first.values)


def test_profile_model_dimension_and_hash_change_output() -> None:
    baseline = DeterministicMockEmbeddingProvider(_profile()).embed(
        [_input("sha256:base")]
    )[0]
    profile_changed = DeterministicMockEmbeddingProvider(
        _profile(profile_id="code_default")
    ).embed([_input("sha256:base")])[0]
    model_changed = DeterministicMockEmbeddingProvider(
        _profile(model_name="mock-v2")
    ).embed([_input("sha256:base")])[0]
    hash_changed = DeterministicMockEmbeddingProvider(_profile()).embed(
        [_input("sha256:other")]
    )[0]
    dimension_changed = DeterministicMockEmbeddingProvider(
        _profile(dimensions=12)
    ).embed([_input("sha256:base")])[0]

    assert baseline.values != profile_changed.values
    assert baseline.values != model_changed.values
    assert baseline.values != hash_changed.values
    assert baseline.values != dimension_changed.values[:8]
    assert dimension_changed.dimensions == 12


def test_mock_provider_logs_safe_diagnostics_only(
    caplog,
) -> None:
    secret_text = "password=hunter2"
    profile = _profile()
    provider = DeterministicMockEmbeddingProvider(profile)

    with caplog.at_level(logging.INFO, logger="idp_brain.embeddings.providers"):
        vector = provider.embed(
            [
                EmbeddingInput(
                    chunk_id=uuid4(),
                    sanitized_text=secret_text,
                    sanitized_content_hash="sha256:safe-hash",
                    metadata={"api_key": "sk-test-secret"},
                )
            ]
        )[0]

    rendered_records = "\n".join(
        f"{record.getMessage()}\n{record.__dict__!r}" for record in caplog.records
    )
    assert "sanitized content only" not in rendered_records
    assert secret_text not in rendered_records
    assert "sk-test-secret" not in rendered_records
    assert repr(vector.values) not in rendered_records
    assert "sha256:safe-hash" in rendered_records
    assert profile.model_name in rendered_records
