"""Provider contracts and registry for sanitized embeddings."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable
from uuid import UUID

from idp_brain.config.models import EmbeddingProfileConfig

logger = logging.getLogger(__name__)

ALLOW_EXTERNAL_MODELS_ENV = "IDP_BRAIN_ALLOW_EXTERNAL_MODELS"


class EmbeddingProviderConfigError(ValueError):
    """Raised when an embedding provider cannot be safely resolved."""


@dataclass(frozen=True, slots=True)
class EmbeddingInput:
    """Sanitized text and safe metadata for one embedding request."""

    chunk_id: UUID
    sanitized_text: str
    sanitized_content_hash: str
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    """Embedding output owned by the application, not a vendor SDK."""

    values: list[float]
    dimensions: int
    provider_id: str
    model_id: str

    def __post_init__(self) -> None:
        if len(self.values) != self.dimensions:
            raise ValueError("embedding vector length must equal dimensions")


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Application-owned embedding provider protocol."""

    provider_id: str
    model_id: str
    dimensions: int

    def embed(self, inputs: Sequence[EmbeddingInput]) -> list[EmbeddingVector]:
        """Embed sanitized inputs."""


class DisabledExternalEmbeddingProvider:
    """Fail-closed placeholder for optional external providers."""

    def __init__(self, profile: EmbeddingProfileConfig) -> None:
        self.provider_id = profile.provider_id
        self.model_id = profile.model_name
        self.dimensions = profile.dimensions
        self._profile = profile

    def embed(self, inputs: Sequence[EmbeddingInput]) -> list[EmbeddingVector]:
        missing_env_vars = [
            name for name in self._profile.required_env_vars if not os.getenv(name)
        ]
        if missing_env_vars:
            joined = ", ".join(sorted(missing_env_vars))
            raise EmbeddingProviderConfigError(
                f"external embedding provider {self.provider_id!r} is missing "
                f"required credential environment variables: {joined}"
            )
        raise EmbeddingProviderConfigError(
            f"external embedding provider {self.provider_id!r} has no local adapter"
        )


class EmbeddingProviderRegistry:
    """Resolve configured embedding providers with external-call gates."""

    def __init__(self, profiles: Sequence[EmbeddingProfileConfig]) -> None:
        self._profiles = {profile.profile_id: profile for profile in profiles}

    def resolve(self, profile_id: str) -> EmbeddingProvider:
        """Resolve a configured provider by profile ID."""

        profile = self._profiles.get(profile_id)
        if profile is None:
            raise EmbeddingProviderConfigError(
                f"unknown embedding profile {profile_id!r}"
            )
        if not profile.enabled:
            raise EmbeddingProviderConfigError(
                f"embedding profile {profile_id!r} is disabled"
            )
        if profile.external and not _external_models_allowed():
            raise EmbeddingProviderConfigError(
                f"external embedding profile {profile_id!r} requires "
                f"{ALLOW_EXTERNAL_MODELS_ENV}=true"
            )
        if profile.provider_id == "mock":
            from idp_brain.embeddings.mock import DeterministicMockEmbeddingProvider

            return DeterministicMockEmbeddingProvider(profile)
        if profile.external:
            return DisabledExternalEmbeddingProvider(profile)
        raise EmbeddingProviderConfigError(
            f"embedding provider {profile.provider_id!r} is not available locally"
        )


def log_embedding_batch(
    *,
    profile: EmbeddingProfileConfig,
    inputs: Sequence[EmbeddingInput],
    elapsed_ms: float,
) -> None:
    """Emit safe provider diagnostics without request text or vectors."""

    logger.info(
        "embedding batch complete",
        extra={
            "provider_id": profile.provider_id,
            "model_id": profile.model_name,
            "dimensions": profile.dimensions,
            "batch_size": profile.batch_size,
            "count": len(inputs),
            "elapsed_ms": round(elapsed_ms, 3),
            "sanitized_content_hashes": [
                item.sanitized_content_hash for item in inputs
            ],
        },
    )


def _external_models_allowed() -> bool:
    return os.getenv(ALLOW_EXTERNAL_MODELS_ENV, "").lower() == "true"
