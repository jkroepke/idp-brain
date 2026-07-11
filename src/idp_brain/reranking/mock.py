"""Deterministic local reranker for CI and retrieval evaluation."""

from __future__ import annotations

import re
from collections.abc import Sequence

from idp_brain.config.models import RerankerProfileConfig
from idp_brain.reranking.providers import RerankerCandidate, RerankerScore

_WORD = re.compile(r"[a-z0-9_]+")


class DeterministicMockReranker:
    def rerank(
        self,
        sanitized_query: str,
        candidates: Sequence[RerankerCandidate],
        profile: RerankerProfileConfig,
    ) -> Sequence[RerankerScore]:
        terms = set(_WORD.findall(sanitized_query.lower()))
        ordered = sorted(
            candidates,
            key=lambda item: (
                -len(terms & set(_WORD.findall(item.sanitized_text.lower()))),
                item.fused_rank,
                item.authority_rank if item.authority_rank is not None else 2**31 - 1,
                -(item.freshness if item.freshness is not None else float("-inf")),
                item.chunk_id,
            ),
        )
        return [
            RerankerScore(chunk_id=item.chunk_id, score=float(len(ordered) - index))
            for index, item in enumerate(ordered)
        ]
