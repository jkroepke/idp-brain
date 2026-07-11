from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from idp_brain.config import load_retrieval_config
from idp_brain.retrieval.models import Candidate, RetrievalFilters, RetrievalQuery
from idp_brain.retrieval.profiles import QueryProfileCatalog
from idp_brain.retrieval.service import HybridRetrievalService


def item(
    chunk_id: str, path: str, rank: int, diagnostics: dict | None = None
) -> Candidate:
    return Candidate(
        chunk_id=chunk_id,
        retrieval_path=path,
        rank=rank,
        matched_fields=(),
        metadata={},
        diagnostics=diagnostics or {},
    )  # type: ignore[arg-type]


class Retriever:
    def __init__(self, candidates: list[Candidate]) -> None:
        self.candidates = candidates

    def retrieve(
        self, query: object, filters: object, profile: object
    ) -> list[Candidate]:
        return self.candidates


def resolved(profile_id: str = "code_qa"):
    return QueryProfileCatalog(
        load_retrieval_config(Path("config/retrieval.yaml"))
    ).resolve(profile_id, embedding_model_id="model", index_version_id="index")


def edge(
    to_id: str,
    *,
    edge_type: str = "references",
    depth: int = 1,
    direction: str = "outbound",
    from_id: str = "seed",
) -> Candidate:
    metadata = {
        "relationship_path": [
            {
                "from_id": from_id,
                "to_id": to_id,
                "relationship_type": edge_type,
                "direction": direction,
                "depth": depth,
                "citation_ids": ["citation"],
                "endpoint_eligible": True,
            }
        ],
        "endpoint_eligible": True,
    }
    return item(to_id, "relationship", 99, metadata)


class Expander:
    def __init__(self, candidates: list[Candidate]) -> None:
        self.candidates = candidates

    def expand(
        self, seeds: object, filters: object, profile: object
    ) -> list[Candidate]:
        return self.candidates


def service(expander: Expander | None = None) -> HybridRetrievalService:
    return HybridRetrievalService(
        exact_retriever=Retriever([item("seed", "exact", 1)]),
        bm25_retriever=Retriever([item("lexical", "bm25", 1)]),
        vector_retriever=Retriever([item("dense", "vector", 1)]),
        relationship_expander=expander,
        reranker=lambda candidates, limit: candidates[:limit],
    )


def test_hybrid_outputs_each_path_and_deterministic_fusion() -> None:
    result = service(Expander([edge("related")])).retrieve(
        RetrievalQuery(query_text="q"), RetrievalFilters(), resolved()
    )
    assert set(result.candidate_lists) == {"exact", "bm25", "vector", "relationship"}
    assert [x.chunk_id for x in result.fused] == [x.chunk_id for x in result.ranked]
    assert result.candidate_lists["relationship"][0].rank == 1


@pytest.mark.parametrize(
    "bad, message",
    [
        (edge("x", edge_type="defines"), "disabled type"),
        (edge("x", depth=2), "depth"),
    ],
)
def test_relationship_profile_bounds_cannot_be_bypassed(
    bad: Candidate, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        service(Expander([bad])).retrieve(
            RetrievalQuery(query_text="q"), RetrievalFilters(), resolved()
        )


def test_relationship_direction_cannot_be_bypassed() -> None:
    profile = resolved()
    config = profile.config.model_copy(
        update={
            "relationship_traversal": profile.config.relationship_traversal.model_copy(
                update={"direction": "outbound"}
            )
        }
    )
    with pytest.raises(ValueError, match="direction"):
        service(Expander([edge("x", direction="inbound")])).retrieve(
            RetrievalQuery(query_text="q"),
            RetrievalFilters(),
            replace(profile, config=config),
        )


def test_relationship_requires_citations_and_eligible_endpoint() -> None:
    bad = edge("x").model_copy(
        update={"diagnostics": {"relationship_path": [], "endpoint_eligible": False}}
    )
    with pytest.raises(ValueError, match="citation-backed"):
        service(Expander([bad])).retrieve(
            RetrievalQuery(query_text="q"), RetrievalFilters(), resolved()
        )


def test_relationship_fanout_and_candidate_limit_are_service_owned() -> None:
    too_many = [edge(f"x{i}") for i in range(9)]
    with pytest.raises(ValueError, match="fanout"):
        service(Expander(too_many)).retrieve(
            RetrievalQuery(query_text="q"), RetrievalFilters(), resolved()
        )


def test_relationship_must_start_from_an_actual_filtered_seed() -> None:
    with pytest.raises(ValueError, match="filtered seed"):
        service(Expander([edge("x", from_id="injected")])).retrieve(
            RetrievalQuery(query_text="q"), RetrievalFilters(), resolved()
        )


def test_malformed_first_relationship_edge_is_rejected_cleanly() -> None:
    malformed = item(
        "x",
        "relationship",
        1,
        {"relationship_path": ["bad"], "endpoint_eligible": True},
    )
    with pytest.raises(ValueError, match="edges must be mappings"):
        service(Expander([malformed])).retrieve(
            RetrievalQuery(query_text="q"), RetrievalFilters(), resolved()
        )


def test_configured_rank_constant_controls_service_fusion() -> None:
    config = load_retrieval_config(Path("config/retrieval.yaml")).model_copy(
        update={"rank_constant": 7}
    )
    profile = QueryProfileCatalog(config).resolve(
        "code_qa", embedding_model_id="model", index_version_id="index"
    )
    result = service(Expander([])).retrieve(
        RetrievalQuery(query_text="q"), RetrievalFilters(), profile
    )
    exact = next(
        candidate for candidate in result.fused if candidate.chunk_id == "seed"
    )
    assert exact.fused_score == pytest.approx(1 / 8)
