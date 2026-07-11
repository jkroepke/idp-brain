"""Application-owned reranker contracts and safety-gated registry."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from numbers import Real
from typing import Protocol

from idp_brain.config.models import RerankerProfileConfig
from idp_brain.ingestion.runs import sanitize_diagnostic_text
from idp_brain.retrieval.models import FusedCandidate

ALLOW_EXTERNAL_MODELS_ENV = "IDP_BRAIN_ALLOW_EXTERNAL_MODELS"


@dataclass(frozen=True)
class RerankerCandidate:
    chunk_id: str
    sanitized_text: str
    sanitized_metadata: Mapping[str, str | int | float | bool | None]
    fused_rank: int
    authority_rank: int | None = None
    freshness: float | None = None


@dataclass(frozen=True)
class RerankerScore:
    chunk_id: str
    score: float


class Reranker(Protocol):
    def rerank(
        self,
        sanitized_query: str,
        candidates: Sequence[RerankerCandidate],
        profile: RerankerProfileConfig,
    ) -> Sequence[RerankerScore]: ...


class RerankerUnavailableError(RuntimeError):
    """Raised without provider payload details when reranking is unavailable."""


class RerankerRegistry:
    def __init__(self, profiles: Sequence[RerankerProfileConfig]) -> None:
        self._profiles = {item.profile_id: item for item in profiles}
        self._providers: dict[str, Reranker] = {}

    def register(self, provider_id: str, provider: Reranker) -> None:
        self._providers[provider_id] = provider

    def profile(self, profile_id: str) -> RerankerProfileConfig | None:
        return self._profiles.get(profile_id)

    def resolve(self, profile_id: str) -> tuple[RerankerProfileConfig, Reranker]:
        profile = self._profiles.get(profile_id)
        if profile is None or not profile.enabled:
            raise RerankerUnavailableError("reranker profile is unavailable")
        if profile.external:
            if os.getenv(ALLOW_EXTERNAL_MODELS_ENV, "").lower() != "true":
                raise RerankerUnavailableError("external model access is disabled")
            if any(not os.getenv(name) for name in profile.required_env_vars):
                raise RerankerUnavailableError("reranker credentials are unavailable")
        provider = self._providers.get(profile.provider_id)
        if provider is None:
            raise RerankerUnavailableError("reranker provider is unavailable")
        return profile, provider


def rerank_fused_candidates(
    *,
    query_text: str,
    candidates: Sequence[FusedCandidate],
    profile_id: str,
    registry: RerankerRegistry,
    candidate_limit: int | None = None,
) -> list[FusedCandidate]:
    """Validate and minimize provider inputs, then preserve fusion lineage."""

    profile, provider = registry.resolve(profile_id)
    sanitized_query = sanitize_diagnostic_text(query_text)
    inputs: list[RerankerCandidate] = []
    truncations = 0
    query_limit = (
        profile.candidate_limit if candidate_limit is None else candidate_limit
    )
    limit = min(profile.candidate_limit, query_limit)
    limited = list(candidates[:limit])
    for fused_rank, candidate in enumerate(limited, 1):
        text = candidate.sanitized_excerpt
        eligibility = candidate.metadata.get("corpus_eligibility_label")
        if not candidate.sanitized_excerpt_trusted or not isinstance(text, str):
            raise ValueError(
                "reranker candidate excerpt is not trusted sanitized output"
            )
        if eligibility not in {"allowed", "default_retrievable", "eligible"}:
            raise ValueError("reranker candidate is not corpus eligible")
        truncated = text[: profile.max_text_length]
        truncations += int(len(truncated) < len(text))
        authority = _candidate_signal(candidate, "authority_rank")
        freshness = _candidate_signal(candidate, "freshness")
        inputs.append(
            RerankerCandidate(
                chunk_id=candidate.chunk_id,
                sanitized_text=truncated,
                sanitized_metadata={
                    key: value
                    for key, value in candidate.metadata.items()
                    if key in {"source_id", "source_type", "version_label"}
                    and isinstance(value, (str, int, float, bool, type(None)))
                },
                fused_rank=fused_rank,
                authority_rank=int(authority) if authority is not None else None,
                freshness=float(freshness) if freshness is not None else None,
            )
        )
    if not inputs:
        return []
    try:
        # Providers own an actually cancellable transport timeout and receive the
        # configured deadline in ``profile.timeout_seconds``.
        scores = list(provider.rerank(sanitized_query, inputs, profile))
    except Exception:
        raise RerankerUnavailableError("reranker provider failed") from None
    expected_ids = [item.chunk_id for item in inputs]
    returned_ids = [item.chunk_id for item in scores]
    if len(returned_ids) != len(set(returned_ids)) or set(returned_ids) != set(
        expected_ids
    ):
        raise RerankerUnavailableError("reranker returned an invalid candidate set")
    if any(
        isinstance(item.score, bool)
        or not isinstance(item.score, Real)
        or not math.isfinite(float(item.score))
        for item in scores
    ):
        raise RerankerUnavailableError("reranker returned invalid scores")
    by_id = {item.chunk_id: item for item in scores}
    ordered = sorted(
        inputs, key=lambda item: (-by_id[item.chunk_id].score, item.chunk_id)
    )
    originals = {item.chunk_id: item for item in limited}
    return [
        originals[item.chunk_id].model_copy(
            update={
                "fused_rank": item.fused_rank,
                "reranked_rank": rank,
                "rerank_score": by_id[item.chunk_id].score,
                "rerank_diagnostics": {"truncated_candidate_count": truncations},
            }
        )
        for rank, item in enumerate(ordered, 1)
    ]


def _candidate_signal(candidate: FusedCandidate, name: str) -> float | None:
    for path_candidate in candidate.path_candidates.values():
        value = path_candidate.diagnostics.get(name)
        if isinstance(value, (int, float)):
            return float(value)
    return None
