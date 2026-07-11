from __future__ import annotations

from idp_brain.config.models import RerankerProfileConfig
from idp_brain.reranking import DeterministicMockReranker, RerankerCandidate


def test_mock_reranker_is_lexical_and_deterministic() -> None:
    candidates = [
        RerankerCandidate("b", "unrelated", {}, 1, 1, 1),
        RerankerCandidate("a", "alpha beta", {}, 2, 2, 2),
    ]
    profile = RerankerProfileConfig(profile_id="p", provider_id="mock", model_name="m")
    expected = ["a", "b"]
    for _ in range(5):
        assert [
            score.chunk_id
            for score in DeterministicMockReranker().rerank(
                "alpha", candidates, profile
            )
        ] == expected
