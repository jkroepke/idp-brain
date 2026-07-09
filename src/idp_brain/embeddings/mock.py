"""Deterministic local embedding provider for CI and development."""

from __future__ import annotations

import hashlib
import math
import time
from collections.abc import Sequence

from idp_brain.config.models import EmbeddingProfileConfig
from idp_brain.embeddings.providers import (
    EmbeddingInput,
    EmbeddingVector,
    log_embedding_batch,
)


class DeterministicMockEmbeddingProvider:
    """Stable hash-based embedding provider with no network access."""

    def __init__(self, profile: EmbeddingProfileConfig) -> None:
        self.profile_id = profile.profile_id
        self.provider_id = profile.provider_id
        self.model_id = profile.model_name
        self.dimensions = profile.dimensions
        self._profile = profile

    def embed(self, inputs: Sequence[EmbeddingInput]) -> list[EmbeddingVector]:
        started = time.perf_counter()
        vectors = [
            EmbeddingVector(
                values=self._values_for(input_item.sanitized_content_hash),
                dimensions=self.dimensions,
                provider_id=self.provider_id,
                model_id=self.model_id,
            )
            for input_item in inputs
        ]
        elapsed_ms = (time.perf_counter() - started) * 1000
        log_embedding_batch(profile=self._profile, inputs=inputs, elapsed_ms=elapsed_ms)
        return vectors

    def _values_for(self, sanitized_content_hash: str) -> list[float]:
        seed = "|".join(
            [
                self.profile_id,
                self.model_id,
                str(self.dimensions),
                sanitized_content_hash,
            ]
        )
        values: list[float] = []
        counter = 0
        while len(values) < self.dimensions:
            digest = hashlib.sha256(f"{seed}|{counter}".encode()).digest()
            for offset in range(0, len(digest), 4):
                integer = int.from_bytes(digest[offset : offset + 4], "big")
                values.append((integer / 0xFFFFFFFF) * 2.0 - 1.0)
                if len(values) == self.dimensions:
                    break
            counter += 1
        return _normalize(values)


def _normalize(values: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in values))
    if magnitude == 0:
        return values
    return [round(value / magnitude, 12) for value in values]
