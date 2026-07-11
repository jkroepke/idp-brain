from __future__ import annotations

from datetime import UTC, datetime

import pytest

from idp_brain.retrieval.fusion import reciprocal_rank_fusion
from idp_brain.retrieval.models import Candidate


def candidate(chunk_id: str, path: str, rank: int, **diagnostics: object) -> Candidate:
    return Candidate(
        chunk_id=chunk_id,
        retrieval_path=path,  # type: ignore[arg-type]
        rank=rank,
        matched_fields=("symbol_path",),
        metadata={"authority_rank": 2, "freshness": 1},
        diagnostics=diagnostics,
    )


def test_single_and_multi_path_rrf_preserves_diagnostics() -> None:
    bm25 = candidate("shared", "bm25", 1, bm25_score=1000.0)
    vector = candidate("shared", "vector", 2, vector_distance=0.001)
    result = reciprocal_rank_fusion(
        {"bm25": [bm25], "vector": [vector]},
        {"bm25": 1.0, "vector": 1.0},
    )
    assert result[0].fused_score == pytest.approx(1 / 61 + 1 / 62)
    assert result[0].path_candidates == {"bm25": bm25, "vector": vector}


def test_scores_from_different_domains_do_not_affect_fusion() -> None:
    first = reciprocal_rank_fusion(
        {
            "bm25": [candidate("a", "bm25", 1, bm25_score=999999.0)],
            "vector": [candidate("b", "vector", 1, vector_distance=0.00001)],
        },
        {"bm25": 1, "vector": 1},
    )
    second = reciprocal_rank_fusion(
        {
            "bm25": [candidate("a", "bm25", 1, bm25_score=-1.0)],
            "vector": [candidate("b", "vector", 1, vector_distance=99999.0)],
        },
        {"bm25": 1, "vector": 1},
    )
    assert [(item.chunk_id, item.fused_score) for item in first] == [
        (item.chunk_id, item.fused_score) for item in second
    ]


def test_weights_missing_paths_duplicates_override_and_ties_are_deterministic() -> None:
    lists = {
        "exact": [
            candidate("b", "exact", 2),
            candidate("a", "exact", 1),
            candidate("a", "exact", 4),
        ],
        "memory": [candidate("memory", "memory", 1)],
    }
    expected = ["a", "b", "memory"]
    for _ in range(5):
        result = reciprocal_rank_fusion(lists, {"exact": 0.5}, rank_constant=10)
        assert [item.chunk_id for item in result] == expected
        assert result[0].fused_score == pytest.approx(0.5 / 11)


def test_invalid_rank_constant_and_weight_are_rejected() -> None:
    with pytest.raises(ValueError, match="rank_constant"):
        reciprocal_rank_fusion({}, {}, 0)
    with pytest.raises(ValueError, match="weights"):
        reciprocal_rank_fusion({"exact": [candidate("a", "exact", 1)]}, {"exact": -1})


def test_real_shaped_diagnostics_drive_configurable_final_signals() -> None:
    authority = candidate("authority", "bm25", 1, authority_rank=1).model_copy(
        update={"metadata": {"first_seen_at": datetime(2025, 1, 1, tzinfo=UTC)}}
    )
    fresh = candidate("fresh", "bm25", 1).model_copy(
        update={
            "metadata": {"first_seen_at": datetime(2026, 1, 1, tzinfo=UTC)},
            "diagnostics": {"authority_rank": 10, "cosine_distance": 0.1},
        }
    )
    lists = {"bm25": [authority, fresh]}
    weights = {"bm25": 1}
    assert reciprocal_rank_fusion(lists, weights)[0].chunk_id == "authority"
    assert (
        reciprocal_rank_fusion(lists, weights, authority_enabled=False)[0].chunk_id
        == "fresh"
    )
    assert (
        reciprocal_rank_fusion(
            lists, weights, authority_enabled=False, freshness_enabled=False
        )[0].chunk_id
        == "authority"
    )
