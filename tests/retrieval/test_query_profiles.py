from __future__ import annotations

from pathlib import Path

import pytest

from idp_brain.config import load_retrieval_config
from idp_brain.retrieval.profiles import (
    QueryProfileCatalog,
    bm25_profile_from_query_profile,
    exact_profile_from_query_profile,
    vector_profile_from_query_profile,
)


def test_profile_catalog_returns_deterministic_profiles() -> None:
    config = load_retrieval_config(Path("config/retrieval.yaml"))
    catalog = QueryProfileCatalog(config)

    first = catalog.get("docs_qa")
    second = catalog.get("docs_qa")

    assert first == second
    assert first.profile_id == "docs_qa"


def test_bm25_stage_profile_uses_typed_query_profile_settings() -> None:
    config = load_retrieval_config(Path("config/retrieval.yaml"))
    profile = config.profile_by_id("api_symbol_lookup")

    bm25_profile = bm25_profile_from_query_profile(profile)

    assert bm25_profile.profile_id == "api_symbol_lookup"
    assert bm25_profile.candidate_limit == profile.candidate_counts.bm25_top_k
    assert bm25_profile.require_active_index is True
    assert bm25_profile.bm25_fields == tuple(profile.bm25_fields)
    assert "symbol_path" in bm25_profile.bm25_fields
    assert "endpoint_path" not in bm25_profile.bm25_fields
    assert "schema_key" not in bm25_profile.bm25_fields


def test_exact_stage_profile_uses_typed_query_profile_settings() -> None:
    config = load_retrieval_config(Path("config/retrieval.yaml"))
    profile = config.profile_by_id("api_symbol_lookup")

    exact_profile = exact_profile_from_query_profile(profile)

    assert exact_profile.profile_id == "api_symbol_lookup"
    assert exact_profile.candidate_limit == profile.candidate_counts.exact_top_k
    assert exact_profile.require_active_index is True
    assert exact_profile.exact_fields == tuple(profile.exact_fields)
    assert "endpoint_path" in exact_profile.exact_fields
    assert "schema_key" in exact_profile.exact_fields
    assert "symbol_path" in exact_profile.exact_fields


def test_vector_stage_profile_uses_embedding_profile_and_limits() -> None:
    config = load_retrieval_config(Path("config/retrieval.yaml"))
    profile = config.profile_by_id("code_qa")

    vector_profile = vector_profile_from_query_profile(
        profile,
        embedding_model_id="embedding-model-v1",
        index_version_id="active-index-v1",
    )

    assert vector_profile.profile_id == "code_qa"
    assert vector_profile.embedding_profile_id == "local-ci-code-embedding"
    assert vector_profile.embedding_model_id == "embedding-model-v1"
    assert vector_profile.index_version_id == "active-index-v1"
    assert vector_profile.candidate_limit == profile.candidate_counts.vector_top_k
    assert vector_profile.require_active_index is True


def test_catalog_resolves_all_stage_limits_from_profile() -> None:
    config = load_retrieval_config(Path("config/retrieval.yaml"))
    catalog = QueryProfileCatalog(config)

    resolved = catalog.resolve(
        "release_change_search",
        embedding_model_id="embedding-model-v2",
        index_version_id="active-index-v2",
    )

    assert resolved.exact_profile.candidate_limit == (
        resolved.config.candidate_counts.exact_top_k
    )
    assert resolved.exact_profile.exact_fields == tuple(resolved.config.exact_fields)
    assert resolved.bm25_profile.candidate_limit == (
        resolved.config.candidate_counts.bm25_top_k
    )
    assert resolved.vector_profile.candidate_limit == (
        resolved.config.candidate_counts.vector_top_k
    )
    assert resolved.fused_limit == resolved.config.candidate_counts.fused_top_k
    assert resolved.rerank_limit == resolved.config.candidate_counts.rerank_top_k


def test_unknown_profile_id_raises_key_error() -> None:
    config = load_retrieval_config(Path("config/retrieval.yaml"))
    catalog = QueryProfileCatalog(config)

    with pytest.raises(KeyError):
        catalog.get("missing_profile")  # type: ignore[arg-type]
