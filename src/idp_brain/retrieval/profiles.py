"""Adapters from typed query profiles to retrieval-stage settings."""

from __future__ import annotations

from dataclasses import dataclass

from idp_brain.config.retrieval import (
    QueryProfileId,
    RetrievalConfig,
    RetrievalQueryProfileConfig,
)
from idp_brain.retrieval.models import BM25RetrievalProfile, VectorRetrievalProfile


@dataclass(frozen=True)
class ExactRetrievalProfile:
    """Exact lookup settings resolved from a typed query profile."""

    profile_id: str
    exact_fields: tuple[str, ...]
    candidate_limit: int
    require_active_index: bool = False


@dataclass(frozen=True)
class ResolvedQueryProfile:
    """Profile settings resolved for exact, BM25, vector, and fusion stages."""

    config: RetrievalQueryProfileConfig
    exact_profile: ExactRetrievalProfile
    bm25_profile: BM25RetrievalProfile
    vector_profile: VectorRetrievalProfile
    fused_limit: int
    rerank_limit: int
    rank_constant: int


class QueryProfileCatalog:
    """Deterministic lookup and stage-profile construction for retrieval profiles."""

    def __init__(self, config: RetrievalConfig) -> None:
        self._profiles = {
            profile.profile_id: profile for profile in config.query_profiles
        }
        self._rank_constant = config.rank_constant

    def get(self, profile_id: QueryProfileId) -> RetrievalQueryProfileConfig:
        """Return one configured query profile."""

        return self._profiles[profile_id]

    def resolve(
        self,
        profile_id: QueryProfileId,
        *,
        embedding_model_id: str,
        index_version_id: str,
    ) -> ResolvedQueryProfile:
        """Resolve a query profile into current retrieval-stage settings."""

        profile = self.get(profile_id)
        return ResolvedQueryProfile(
            config=profile,
            exact_profile=exact_profile_from_query_profile(profile),
            bm25_profile=bm25_profile_from_query_profile(profile),
            vector_profile=vector_profile_from_query_profile(
                profile,
                embedding_model_id=embedding_model_id,
                index_version_id=index_version_id,
            ),
            fused_limit=profile.candidate_counts.fused_top_k,
            rerank_limit=profile.candidate_counts.rerank_top_k,
            rank_constant=self._rank_constant,
        )


def exact_profile_from_query_profile(
    profile: RetrievalQueryProfileConfig,
) -> ExactRetrievalProfile:
    """Build exact lookup settings from a typed query profile."""

    return ExactRetrievalProfile(
        profile_id=profile.profile_id,
        exact_fields=tuple(profile.exact_fields),
        candidate_limit=profile.candidate_counts.exact_top_k,
        require_active_index=profile.active_index_behavior.require_filter,
    )


def bm25_profile_from_query_profile(
    profile: RetrievalQueryProfileConfig,
) -> BM25RetrievalProfile:
    """Build BM25 retrieval settings from a typed query profile."""

    return BM25RetrievalProfile(
        profile_id=profile.profile_id,
        bm25_fields=tuple(profile.bm25_fields),
        candidate_limit=profile.candidate_counts.bm25_top_k,
        require_active_index=profile.active_index_behavior.require_filter,
    )


def vector_profile_from_query_profile(
    profile: RetrievalQueryProfileConfig,
    *,
    embedding_model_id: str,
    index_version_id: str,
) -> VectorRetrievalProfile:
    """Build vector retrieval settings from a typed query profile."""

    return VectorRetrievalProfile(
        profile_id=profile.profile_id,
        embedding_profile_id=profile.embedding_profile_id,
        embedding_model_id=embedding_model_id,
        index_version_id=index_version_id,
        candidate_limit=profile.candidate_counts.vector_top_k,
        require_active_index=profile.active_index_behavior.require_filter,
    )
