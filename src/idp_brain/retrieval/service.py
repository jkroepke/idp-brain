"""Hybrid retrieval orchestration with bounded relationship expansion."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from idp_brain.config.retrieval import RetrievalQueryProfileConfig
from idp_brain.reranking.providers import (
    RerankerRegistry,
    RerankerUnavailableError,
    rerank_fused_candidates,
)
from idp_brain.retrieval.fusion import reciprocal_rank_fusion
from idp_brain.retrieval.models import (
    Candidate,
    FusedCandidate,
    RetrievalFilters,
    RetrievalQuery,
)
from idp_brain.retrieval.profiles import ResolvedQueryProfile


class CandidateRetriever(Protocol):
    def retrieve(
        self, query: RetrievalQuery, filters: RetrievalFilters, profile: object
    ) -> list[Candidate]: ...


class RelationshipExpander(Protocol):
    def expand(
        self,
        seeds: Sequence[Candidate],
        filters: RetrievalFilters,
        profile: RetrievalQueryProfileConfig,
    ) -> list[Candidate]: ...


@dataclass(frozen=True)
class HybridRetrievalResult:
    """Path-specific evaluation output and the fused/reranked candidate list."""

    candidate_lists: Mapping[str, tuple[Candidate, ...]]
    fused: tuple[FusedCandidate, ...]
    ranked: tuple[FusedCandidate, ...]


class HybridRetrievalService:
    """Obtain trusted path candidates, optionally expand, and fuse them."""

    def __init__(
        self,
        *,
        exact_retriever: CandidateRetriever,
        bm25_retriever: CandidateRetriever,
        vector_retriever: CandidateRetriever,
        relationship_expander: RelationshipExpander | None = None,
        reranker: Callable[[Sequence[FusedCandidate], int], Sequence[FusedCandidate]]
        | None = None,
        reranker_registry: RerankerRegistry | None = None,
        rank_constant: int | None = None,
    ) -> None:
        self._exact = exact_retriever
        self._bm25 = bm25_retriever
        self._vector = vector_retriever
        self._relationships = relationship_expander
        self._reranker = reranker
        self._reranker_registry = reranker_registry
        self._rank_constant = rank_constant

    def retrieve(
        self,
        query: RetrievalQuery,
        filters: RetrievalFilters,
        profile: ResolvedQueryProfile,
    ) -> HybridRetrievalResult:
        paths: dict[str, list[Candidate]] = {
            "exact": self._exact.retrieve(query, filters, profile.exact_profile),
            "bm25": self._bm25.retrieve(query, filters, profile.bm25_profile),
            "vector": self._vector.retrieve(query, filters, profile.vector_profile),
        }
        traversal = profile.config.relationship_traversal
        if traversal.enabled:
            if self._relationships is None:
                raise ValueError("enabled relationship traversal requires an expander")
            seeds = self._relationship_seeds(paths, profile)
            expanded = self._relationships.expand(seeds, filters, profile.config)
            paths["relationship"] = self._validate_relationship_candidates(
                expanded, profile, {seed.chunk_id for seed in seeds}
            )

        weights = profile.config.fusion_weights.model_dump()
        rank_constant = self._rank_constant or profile.rank_constant
        fused = reciprocal_rank_fusion(
            paths,
            weights,
            rank_constant,
            authority_enabled=profile.config.authority_weighting.enabled,
            freshness_enabled=profile.config.freshness_weighting.enabled,
        )[: profile.fused_limit]
        ranked: Sequence[FusedCandidate] = fused
        reranker_profile_id = profile.config.reranker_profile_id
        if self._reranker_registry is not None and reranker_profile_id:
            reranker_profile = self._reranker_registry.profile(reranker_profile_id)
            try:
                ranked = rerank_fused_candidates(
                    query_text=query.query_text,
                    candidates=fused,
                    profile_id=reranker_profile_id,
                    registry=self._reranker_registry,
                    candidate_limit=profile.rerank_limit,
                )
            except RerankerUnavailableError:
                if reranker_profile is None or not reranker_profile.allow_fallback:
                    raise
        elif self._reranker is not None and reranker_profile_id:
            ranked = self._reranker(fused, profile.rerank_limit)
        elif reranker_profile_id:
            raise RerankerUnavailableError("required reranker is unavailable")
        return HybridRetrievalResult(
            candidate_lists={key: tuple(value) for key, value in paths.items()},
            fused=tuple(fused),
            ranked=tuple(ranked),
        )

    def _relationship_seeds(
        self, paths: Mapping[str, list[Candidate]], profile: ResolvedQueryProfile
    ) -> list[Candidate]:
        sources = profile.config.relationship_traversal.seed_sources
        seeds = [
            candidate
            for source in sources
            if source != "fused"
            for candidate in paths.get(source, ())
        ]
        if "fused" in sources:
            preliminary = reciprocal_rank_fusion(
                paths,
                profile.config.fusion_weights.model_dump(),
                self._rank_constant or profile.rank_constant,
            )
            seeds.extend(
                min(item.path_candidates.values(), key=lambda candidate: candidate.rank)
                for item in preliminary
            )
        seen: set[str] = set()
        return [
            candidate
            for candidate in seeds
            if not (candidate.chunk_id in seen or seen.add(candidate.chunk_id))
        ]

    @staticmethod
    def _validate_relationship_candidates(
        candidates: Sequence[Candidate],
        profile: ResolvedQueryProfile,
        seed_ids: set[str],
    ) -> list[Candidate]:
        traversal = profile.config.relationship_traversal
        limit = traversal.max_relationship_candidates
        valid: list[Candidate] = []
        seen: set[str] = set()
        fanout: dict[tuple[str, int], set[str]] = {}
        for candidate in candidates:
            diagnostics = candidate.diagnostics
            if candidate.retrieval_path != "relationship":
                raise ValueError(
                    "relationship expander returned a non-relationship candidate"
                )
            path = diagnostics.get("relationship_path")
            if not isinstance(path, (list, tuple)) or not path:
                raise ValueError(
                    "relationship candidates must be citation-backed with path metadata"
                )
            if not diagnostics.get("endpoint_eligible", False):
                raise ValueError(
                    "relationship endpoint did not pass corpus eligibility"
                )
            first_edge = path[0]
            if not isinstance(first_edge, dict):
                raise ValueError("relationship path edges must be mappings")
            if first_edge.get("from_id") not in seed_ids:
                raise ValueError(
                    "relationship path does not start from a filtered seed"
                )
            previous_to: str | None = None
            for depth, edge in enumerate(path, 1):
                if not isinstance(edge, dict):
                    raise ValueError("relationship path edges must be mappings")
                if depth > traversal.max_depth or edge.get("depth") != depth:
                    raise ValueError("relationship candidate exceeds traversal depth")
                if edge.get("relationship_type") not in traversal.relationship_types:
                    raise ValueError("relationship candidate uses a disabled type")
                if edge.get("direction") not in (
                    {"outbound", "inbound"}
                    if traversal.direction == "both"
                    else {traversal.direction}
                ):
                    raise ValueError("relationship candidate uses a disabled direction")
                if not edge.get("citation_ids") or not edge.get("endpoint_eligible"):
                    raise ValueError("relationship edge is uncited or ineligible")
                from_id, to_id = edge.get("from_id"), edge.get("to_id")
                if not isinstance(from_id, str) or not isinstance(to_id, str):
                    raise ValueError(
                        "relationship edge identifiers must be sanitized IDs"
                    )
                if previous_to is not None and from_id != previous_to:
                    raise ValueError("relationship path is not contiguous")
                previous_to = to_id
                fanout.setdefault((from_id, depth), set()).add(to_id)
                if len(fanout[(from_id, depth)]) > traversal.max_fanout_per_seed:
                    raise ValueError("relationship candidate exceeds traversal fanout")
            visited = [path[0]["from_id"], *(edge["to_id"] for edge in path)]
            if len(visited) != len(set(visited)):
                raise ValueError("relationship candidate contains a cycle")
            if candidate.chunk_id != path[-1]["to_id"]:
                raise ValueError(
                    "relationship candidate ID does not match its endpoint"
                )
            if candidate.chunk_id not in seen:
                seen.add(candidate.chunk_id)
                valid.append(candidate.model_copy(update={"rank": len(valid) + 1}))
            if len(valid) >= limit:
                break
        return valid
