from __future__ import annotations

import math

import pytest

from idp_brain.config.models import RerankerProfileConfig
from idp_brain.reranking import DeterministicMockReranker, RerankerRegistry
from idp_brain.reranking.providers import rerank_fused_candidates
from idp_brain.retrieval.models import Candidate, FusedCandidate


def fused(chunk_id: str, text: str, eligible: str = "eligible") -> FusedCandidate:
    path = Candidate(
        chunk_id=chunk_id,
        retrieval_path="bm25",
        rank=1,
        matched_fields=(),
        metadata={},
        diagnostics={"authority_rank": 1},
    )
    return FusedCandidate(
        chunk_id=chunk_id,
        fused_score=1,
        path_candidates={"bm25": path},
        metadata={"corpus_eligibility_label": eligible},
        sanitized_excerpt=text,
        sanitized_excerpt_trusted=True,
    )


def registry(**updates: object) -> RerankerRegistry:
    profile = RerankerProfileConfig(
        profile_id="p", provider_id="mock", model_name="m", max_text_length=5, **updates
    )
    result = RerankerRegistry([profile])
    result.register("mock", DeterministicMockReranker())
    return result


def test_reranking_preserves_fusion_and_records_safe_truncation_count() -> None:
    result = rerank_fused_candidates(
        query_text="alpha",
        candidates=[fused("a", "alpha long")],
        profile_id="p",
        registry=registry(),
    )
    assert result[0].fused_score == 1
    assert result[0].fused_rank == result[0].reranked_rank == 1
    assert result[0].rerank_diagnostics == {"truncated_candidate_count": 1}


@pytest.mark.parametrize(
    "candidate",
    [
        fused("x", "arbitrary raw content").model_copy(
            update={"sanitized_excerpt_trusted": False}
        ),
        fused("x", "safe", "blocked"),
    ],
)
def test_unsafe_or_ineligible_candidates_are_rejected(
    candidate: FusedCandidate,
) -> None:
    with pytest.raises(ValueError):
        rerank_fused_candidates(
            query_text="q", candidates=[candidate], profile_id="p", registry=registry()
        )


class CapturingProvider:
    def __init__(self, scores: object = None) -> None:
        self.seen = []
        self.scores = scores

    def rerank(self, query: object, candidates: object, profile: object):
        self.seen = list(candidates)  # type: ignore[arg-type]
        if self.scores is not None:
            return self.scores
        from idp_brain.reranking import RerankerScore

        return [RerankerScore(item.chunk_id, 1.0) for item in self.seen]


def test_benign_long_trusted_excerpt_is_accepted_then_truncated() -> None:
    provider = CapturingProvider()
    active = registry()
    active.register("mock", provider)
    rerank_fused_candidates(
        query_text="q",
        candidates=[fused("x", "a" * 300)],
        profile_id="p",
        registry=active,
    )
    assert provider.seen[0].sanitized_text == "a" * 5


def test_boundary_applies_minimum_candidate_limit() -> None:
    provider = CapturingProvider()
    active = registry(candidate_limit=4)
    active.register("mock", provider)
    result = rerank_fused_candidates(
        query_text="q",
        candidates=[fused(str(index), "safe") for index in range(5)],
        profile_id="p",
        registry=active,
        candidate_limit=2,
    )
    assert len(provider.seen) == len(result) == 2


def test_explicit_zero_query_candidate_limit_sends_and_returns_nothing() -> None:
    provider = CapturingProvider()
    active = registry(candidate_limit=4)
    active.register("mock", provider)
    result = rerank_fused_candidates(
        query_text="q",
        candidates=[fused("x", "safe")],
        profile_id="p",
        registry=active,
        candidate_limit=0,
    )
    assert provider.seen == []
    assert result == []


@pytest.mark.parametrize(
    "scores",
    [
        [("duplicate", 1.0), ("duplicate", 2.0)],
        [("extra", 1.0)],
        [("x", True)],
        [("x", math.nan)],
        [("x", math.inf)],
    ],
)
def test_malicious_provider_results_are_rejected(
    scores: list[tuple[str, object]],
) -> None:
    from idp_brain.reranking import RerankerScore, RerankerUnavailableError

    provider = CapturingProvider(
        [RerankerScore(chunk_id, score) for chunk_id, score in scores]
    )
    active = registry()
    active.register("mock", provider)
    with pytest.raises(RerankerUnavailableError):
        rerank_fused_candidates(
            query_text="q",
            candidates=[fused("x", "safe")],
            profile_id="p",
            registry=active,
        )


def test_provider_secret_error_is_not_chained() -> None:
    from idp_brain.reranking import RerankerUnavailableError

    class Failing:
        def rerank(self, query: object, candidates: object, profile: object):
            raise RuntimeError("secret raw response and candidate text")

    active = registry()
    active.register("mock", Failing())
    with pytest.raises(RerankerUnavailableError) as caught:
        rerank_fused_candidates(
            query_text="q",
            candidates=[fused("x", "safe")],
            profile_id="p",
            registry=active,
        )
    assert caught.value.__cause__ is None
    assert "secret" not in str(caught.value)


def test_provider_lifecycle_completes_before_boundary_returns() -> None:
    class LifecycleProvider(CapturingProvider):
        completed = False

        def rerank(self, query: object, candidates: object, profile: object):
            result = super().rerank(query, candidates, profile)
            self.completed = True
            return result

    provider = LifecycleProvider()
    active = registry()
    active.register("mock", provider)
    rerank_fused_candidates(
        query_text="q", candidates=[fused("x", "safe")], profile_id="p", registry=active
    )
    assert provider.completed is True
