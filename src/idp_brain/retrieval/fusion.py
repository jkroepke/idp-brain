"""Pure reciprocal-rank fusion for sanitized retrieval candidates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from idp_brain.retrieval.models import Candidate, FusedCandidate

DEFAULT_RANK_CONSTANT = 60


def reciprocal_rank_fusion(
    candidate_lists: Mapping[str, Sequence[Candidate]],
    weights: Mapping[str, float],
    rank_constant: int = DEFAULT_RANK_CONSTANT,
    *,
    authority_enabled: bool = True,
    freshness_enabled: bool = True,
) -> list[FusedCandidate]:
    """Fuse path-ranked candidates without mixing their score domains."""

    if rank_constant <= 0:
        raise ValueError("rank_constant must be positive")
    scores: dict[str, float] = {}
    paths: dict[str, dict[str, Candidate]] = {}
    metadata: dict[str, dict[str, object]] = {}
    for path in sorted(candidate_lists):
        weight = weights.get(path, 0.0)
        if weight < 0:
            raise ValueError("fusion weights cannot be negative")
        # A repeated ID in one path contributes once, at its best rank.
        best = {}
        for candidate in candidate_lists[path]:
            current = best.get(candidate.chunk_id)
            if current is None or candidate.rank < current.rank:
                best[candidate.chunk_id] = candidate
        for chunk_id, candidate in best.items():
            scores[chunk_id] = scores.get(chunk_id, 0.0) + weight / (
                rank_constant + candidate.rank
            )
            paths.setdefault(chunk_id, {})[path] = candidate
            metadata.setdefault(chunk_id, dict(candidate.metadata))

    fused = [
        FusedCandidate(
            chunk_id=chunk_id,
            fused_score=score,
            path_candidates=paths[chunk_id],
            metadata=metadata[chunk_id],
        )
        for chunk_id, score in scores.items()
    ]
    return sorted(
        fused,
        key=lambda candidate: _sort_key(
            candidate,
            authority_enabled=authority_enabled,
            freshness_enabled=freshness_enabled,
        ),
    )


def _sort_key(
    candidate: FusedCandidate,
    *,
    authority_enabled: bool,
    freshness_enabled: bool,
) -> tuple[object, ...]:
    def rank(path: str) -> int:
        item = candidate.path_candidates.get(path)
        return item.rank if item else 2**31 - 1

    authority_values = [
        value
        for item in candidate.path_candidates.values()
        if isinstance(
            (
                value := item.diagnostics.get(
                    "authority_rank", item.metadata.get("authority_rank")
                )
            ),
            (int, float),
        )
    ]
    freshness_values = [
        value.timestamp() if isinstance(value, datetime) else value
        for item in candidate.path_candidates.values()
        if isinstance(
            (
                value := item.metadata.get(
                    "first_seen_at", item.diagnostics.get("freshness")
                )
            ),
            (int, float, datetime),
        )
    ]
    authority = min(authority_values, default=float("inf"))
    freshness = max(freshness_values, default=float("-inf"))
    return (
        -candidate.fused_score,
        rank("exact"),
        rank("bm25"),
        rank("vector"),
        authority if authority_enabled else 0,
        -freshness if freshness_enabled else 0,
        candidate.chunk_id,
    )
