from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from idp_brain.config import (
    ConfigReferenceError,
    load_config_dir,
    load_retrieval_config,
)
from idp_brain.config.retrieval import (
    REQUIRED_FILTER_DIMENSIONS,
    REQUIRED_QUERY_PROFILE_IDS,
    RetrievalConfig,
)
from idp_brain.retrieval.models import BM25_RETRIEVAL_FIELDS


def test_example_retrieval_config_loads_required_profiles() -> None:
    config = load_retrieval_config(Path("config/retrieval.yaml"))

    assert {profile.profile_id for profile in config.query_profiles} == (
        REQUIRED_QUERY_PROFILE_IDS
    )
    for profile in config.query_profiles:
        assert set(profile.filter_dimensions) >= REQUIRED_FILTER_DIMENSIONS
        assert profile.active_index_behavior.require_filter is True
        assert profile.fusion_method == "reciprocal_rank_fusion"
        assert profile.diagnostics.enabled is True
        assert profile.diagnostics.include_scores is False
        assert 0 <= profile.candidate_counts.exact_top_k <= 50
        assert 50 <= profile.candidate_counts.bm25_top_k <= 200
        assert 50 <= profile.candidate_counts.vector_top_k <= 200
        assert profile.candidate_counts.rerank_top_k <= (
            profile.candidate_counts.fused_top_k
        )


def test_relationship_traversal_is_disabled_unless_explicitly_enabled() -> None:
    config = load_retrieval_config(Path("config/retrieval.yaml"))

    traversal_by_profile = {
        profile.profile_id: profile.relationship_traversal
        for profile in config.query_profiles
    }

    assert traversal_by_profile["docs_qa"].enabled is False
    assert traversal_by_profile["docs_qa"].relationship_types == []
    for profile_id in (
        "code_qa",
        "api_symbol_lookup",
        "release_change_search",
        "conflict_search",
    ):
        traversal = traversal_by_profile[profile_id]
        assert traversal.enabled is True
        assert 1 <= traversal.max_depth <= 3
        assert 1 <= traversal.max_fanout_per_seed <= 25
        assert 1 <= traversal.max_relationship_candidates <= 100
        assert traversal.seed_sources


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (
            ("query_profiles", 0, "candidate_counts", "bm25_top_k"),
            0,
            "greater than or equal to 50",
        ),
        (
            ("query_profiles", 0, "candidate_counts", "bm25_top_k"),
            49,
            "greater than or equal to 50",
        ),
        (
            ("query_profiles", 0, "candidate_counts", "vector_top_k"),
            201,
            "less than or equal to 200",
        ),
        (
            ("query_profiles", 0, "fusion_method"),
            "raw_score_sum",
            "fusion_method",
        ),
        (
            ("query_profiles", 0, "bm25_fields"),
            ["raw_bm25_score"],
            "unknown retrieval field",
        ),
        (
            ("query_profiles", 2, "bm25_fields"),
            ["schema_key"],
            "not backed by the chunks BM25 index",
        ),
        (
            ("query_profiles", 1, "relationship_traversal", "max_depth"),
            4,
            "less than or equal to 3",
        ),
        (
            ("query_profiles", 1, "relationship_traversal", "relationship_types"),
            ["unknown_edge"],
            "unknown relationship type",
        ),
        (
            ("query_profiles", 0, "filter_dimensions"),
            [
                "source_allowlist",
                "visibility",
                "sensitivity_class",
                "license_policy_status",
                "version_or_release_scope",
            ],
            "active_index_version",
        ),
    ],
)
def test_invalid_retrieval_profiles_fail_with_actionable_errors(
    path: tuple[str | int, ...],
    value: Any,
    message: str,
) -> None:
    payload = _example_payload()
    _assign(payload, path, value)

    with pytest.raises(ValidationError) as exc_info:
        RetrievalConfig.model_validate(payload)

    assert message in str(exc_info.value)


def test_cross_file_validation_rejects_missing_embedding_reference(
    tmp_path: Path,
) -> None:
    config_dir = _copy_config_dir(tmp_path)
    retrieval_path = config_dir / "retrieval.yaml"
    payload = _example_payload()
    payload["query_profiles"][0]["embedding_profile_id"] = "missing-embedding"
    retrieval_path.write_text(_dump_yaml(payload), encoding="utf-8")

    with pytest.raises(ConfigReferenceError) as exc_info:
        load_config_dir(config_dir)

    message = str(exc_info.value)
    assert "missing-embedding" in message
    assert "retrieval profile 'docs_qa'" in message


def test_cross_file_validation_rejects_missing_reranker_reference(
    tmp_path: Path,
) -> None:
    config_dir = _copy_config_dir(tmp_path)
    retrieval_path = config_dir / "retrieval.yaml"
    payload = _example_payload()
    payload["query_profiles"][1]["reranker_profile_id"] = "missing-reranker"
    retrieval_path.write_text(_dump_yaml(payload), encoding="utf-8")

    with pytest.raises(ConfigReferenceError) as exc_info:
        load_config_dir(config_dir)

    message = str(exc_info.value)
    assert "missing-reranker" in message
    assert "retrieval profile 'code_qa'" in message


def test_bm25_profile_fields_are_index_backed() -> None:
    config = load_retrieval_config(Path("config/retrieval.yaml"))
    indexed_fields = set(BM25_RETRIEVAL_FIELDS)

    for profile in config.query_profiles:
        assert set(profile.bm25_fields) <= indexed_fields

    api_profile = config.profile_by_id("api_symbol_lookup")
    assert "schema_key" in api_profile.exact_fields
    assert "schema_key" not in api_profile.bm25_fields


def _example_payload() -> dict[str, Any]:
    import yaml

    return yaml.safe_load(Path("config/retrieval.yaml").read_text(encoding="utf-8"))


def _assign(payload: dict[str, Any], path: tuple[str | int, ...], value: Any) -> None:
    target: Any = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


def _copy_config_dir(tmp_path: Path) -> Path:
    import shutil

    target = tmp_path / "config"
    shutil.copytree(Path("config"), target)
    return target


def _dump_yaml(payload: dict[str, Any]) -> str:
    import yaml

    return yaml.safe_dump(deepcopy(payload), sort_keys=True)
