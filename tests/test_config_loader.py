from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from idp_brain.config import (
    ConfigFileNotFoundError,
    ConfigReferenceError,
    ConfigValidationError,
    load_config_dir,
)

ConfigData = dict[str, dict[str, Any]]


def _query_profile(profile_id: str) -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "exact_fields": ["source_id", "artifact_path"],
        "bm25_fields": ["sanitized_text", "heading_path"],
        "vector_index": "docs",
        "embedding_model": "local-embedding",
        "candidate_counts": {
            "exact_top_k": 5,
            "bm25_top_k": 20,
            "vector_top_k": 20,
            "fused_top_k": 20,
            "rerank_top_k": 10,
        },
        "fusion_method": "reciprocal_rank_fusion",
        "reranker": "local-reranker",
        "freshness_weighting": {
            "enabled": True,
            "weight": 0.25,
            "strategy": "decay",
        },
        "authority_weighting": {
            "enabled": True,
            "weight": 0.75,
            "strategy": "source_priority",
        },
        "token_budget": 1200,
    }


def _minimal_config() -> ConfigData:
    return {
        "sources": {
            "config_version": 1,
            "kind": "sources",
            "sources": [
                {
                    "source_id": "local-docs",
                    "source_type": "documentation_file",
                    "local_path": "docs/example.md",
                    "tracked_refs": ["main"],
                    "version_strategy": "explicit_refs",
                    "include_paths": ["docs/**"],
                    "exclude_paths": [],
                    "extractor_profile": "docs",
                    "source_priority": 10,
                    "visibility_label": "public",
                    "corpus_eligibility": "default_retrievable",
                    "allowed_groups": ["developers"],
                    "allowed_principals": [],
                    "sensitivity_class": "public",
                    "license_policy": "allowed",
                    "refresh_cadence": "manual",
                }
            ],
        },
        "extractors": {
            "config_version": 1,
            "kind": "extractors",
            "profiles": [
                {
                    "profile_id": "docs",
                    "family": "docs",
                    "file_patterns": ["*.md", "*.html"],
                    "tools": [
                        {
                            "tool_id": "markdown-parser",
                            "enabled": True,
                            "command": [],
                            "options": {"preserve_headings": True},
                        }
                    ],
                    "validator_commands": [
                        {
                            "command_id": "docs-lint",
                            "command": ["docs-lint", "--check"],
                            "enabled": False,
                            "timeout_seconds": 30,
                        }
                    ],
                }
            ],
        },
        "models": {
            "config_version": 1,
            "kind": "models",
            "embedding_profiles": [
                {
                    "model_id": "local-embedding",
                    "provider": "mock",
                    "provider_model_id": "mock-embedding",
                    "enabled": True,
                    "external": False,
                    "deterministic": True,
                    "dimensions": 8,
                }
            ],
            "reranker_profiles": [
                {
                    "model_id": "local-reranker",
                    "provider": "mock",
                    "provider_model_id": "mock-reranker",
                    "enabled": True,
                    "external": False,
                    "deterministic": True,
                }
            ],
            "generator_profiles": [
                {
                    "model_id": "disabled-external-generator",
                    "provider": "openai",
                    "provider_model_id": "gpt-example",
                    "enabled": False,
                    "external": True,
                    "deterministic": False,
                }
            ],
            "provider_routes": [
                {
                    "route_id": "default-embedding",
                    "purpose": "embedding",
                    "primary_model": "local-embedding",
                },
                {
                    "route_id": "default-reranker",
                    "purpose": "reranker",
                    "primary_model": "local-reranker",
                },
            ],
            "budgets": {
                "max_embedding_tokens_per_item": 512,
                "max_rerank_candidates": 25,
                "max_generator_context_tokens": 0,
                "max_external_requests_per_run": 0,
            },
        },
        "retrieval": {
            "config_version": 1,
            "kind": "retrieval",
            "query_profiles": [
                _query_profile("docs_qa"),
                _query_profile("code_qa"),
                _query_profile("api_symbol_lookup"),
                _query_profile("release_change_search"),
                _query_profile("conflict_search"),
            ],
        },
        "evaluation": {
            "config_version": 1,
            "kind": "evaluation",
            "mode": "diagnostic",
            "fixtures": [],
            "thresholds": [],
            "embedding_fine_tuning": {
                "enabled": False,
                "candidate_models": [],
            },
        },
        "security": {
            "config_version": 1,
            "kind": "security",
            "source_allowlist": {
                "mode": "explicit",
                "source_ids": ["local-docs"],
            },
            "redaction_rules": [
                {
                    "rule_id": "secret-like-values",
                    "marker": "[REDACTED_SECRET]",
                    "detector": "regex",
                    "enabled": True,
                    "severity": "high",
                }
            ],
            "pii_profiles": [],
            "prompt_injection": {
                "enabled": True,
                "action": "quarantine",
                "source_text_is_instruction": False,
            },
        },
        "access": {
            "config_version": 1,
            "kind": "access",
            "visibility_labels": [
                {
                    "label": "public",
                    "description": "Public test fixture content.",
                    "rank": 0,
                }
            ],
            "sensitivity_labels": [
                {
                    "label": "public",
                    "description": "No sensitive content expected.",
                    "rank": 0,
                }
            ],
            "license_policy_labels": [
                {
                    "label": "allowed",
                    "description": "Allowed for retrieval fixtures.",
                    "rank": 0,
                }
            ],
            "acl_policies": [
                {
                    "policy_id": "public-docs",
                    "visibility_label": "public",
                    "allowed_groups": ["developers"],
                    "allowed_principals": [],
                    "source_ids": ["local-docs"],
                    "default_deny": True,
                }
            ],
            "default_deny": True,
            "unknown_label_policy": "deny",
        },
        "memory": {
            "config_version": 1,
            "kind": "memory",
            "scopes": [
                {
                    "scope": "session",
                    "enabled": True,
                    "visibility_label": "public",
                    "sensitivity_class": "public",
                    "retention_policy": "short-lived",
                }
            ],
            "retention_policies": [
                {
                    "policy_id": "short-lived",
                    "ttl_days": 30,
                    "max_items": 100,
                    "redact_before_storage": True,
                }
            ],
            "promotion_rules": [
                {
                    "rule_id": "operator-approved-decision",
                    "memory_type": "decision",
                    "requires_operator_approval": True,
                    "required_citations": True,
                    "min_confidence": 0.8,
                }
            ],
            "retrieval_influence": {
                "enabled": False,
                "allowed_scopes": [],
                "max_boost": 0,
                "token_budget": 0,
            },
        },
    }


def _write_config_dir(tmp_path: Path, config: ConfigData) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    for name, data in config.items():
        path = config_dir / f"{name}.yaml"
        path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
    return config_dir


def test_valid_minimal_config_loads(tmp_path: Path) -> None:
    config_dir = _write_config_dir(tmp_path, _minimal_config())

    bundle = load_config_dir(config_dir)

    assert bundle.sources.sources[0].source_id == "local-docs"
    assert bundle.models.embedding_profiles[0].deterministic is True
    assert bundle.models.generator_profiles[0].external is True
    assert bundle.models.generator_profiles[0].enabled is False
    assert {profile.profile_id for profile in bundle.retrieval.query_profiles} == {
        "docs_qa",
        "code_qa",
        "api_symbol_lookup",
        "release_change_search",
        "conflict_search",
    }


def test_missing_files_include_paths(tmp_path: Path) -> None:
    config_dir = _write_config_dir(tmp_path, _minimal_config())
    (config_dir / "memory.yaml").unlink()

    with pytest.raises(ConfigFileNotFoundError) as exc_info:
        load_config_dir(config_dir)

    assert "required config files are missing" in str(exc_info.value)
    assert "memory.yaml" in str(exc_info.value)


def test_invalid_config_version_is_rejected(tmp_path: Path) -> None:
    config = _minimal_config()
    config["sources"]["config_version"] = 2
    config_dir = _write_config_dir(tmp_path, config)

    with pytest.raises(ConfigValidationError) as exc_info:
        load_config_dir(config_dir)

    message = str(exc_info.value)
    assert "sources.yaml" in message
    assert "config_version" in message


def test_unknown_keys_are_rejected(tmp_path: Path) -> None:
    config = _minimal_config()
    config["sources"]["unexpected"] = "not allowed"
    config_dir = _write_config_dir(tmp_path, config)

    with pytest.raises(ConfigValidationError) as exc_info:
        load_config_dir(config_dir)

    message = str(exc_info.value)
    assert "sources.yaml" in message
    assert "unexpected" in message


def test_duplicate_source_ids_are_rejected(tmp_path: Path) -> None:
    config = _minimal_config()
    sources = cast(list[dict[str, Any]], config["sources"]["sources"])
    sources.append(deepcopy(sources[0]))
    config_dir = _write_config_dir(tmp_path, config)

    with pytest.raises(ConfigReferenceError) as exc_info:
        load_config_dir(config_dir)

    message = str(exc_info.value)
    assert "duplicate source IDs" in message
    assert "local-docs" in message
    assert "sources.yaml" in message


def test_unknown_extractor_profile_references_are_rejected(tmp_path: Path) -> None:
    config = _minimal_config()
    source = cast(list[dict[str, Any]], config["sources"]["sources"])[0]
    source["extractor_profile"] = "missing-profile"
    config_dir = _write_config_dir(tmp_path, config)

    with pytest.raises(ConfigReferenceError) as exc_info:
        load_config_dir(config_dir)

    message = str(exc_info.value)
    assert "unknown extractor profile" in message
    assert "missing-profile" in message
    assert "sources.yaml" in message


def test_unknown_model_references_are_rejected(tmp_path: Path) -> None:
    config = _minimal_config()
    retrieval_profile = cast(
        list[dict[str, Any]],
        config["retrieval"]["query_profiles"],
    )[0]
    retrieval_profile["embedding_model"] = "missing-embedding"
    config_dir = _write_config_dir(tmp_path, config)

    with pytest.raises(ConfigReferenceError) as exc_info:
        load_config_dir(config_dir)

    message = str(exc_info.value)
    assert "unknown embedding model" in message
    assert "missing-embedding" in message
    assert "retrieval.yaml" in message


def test_external_model_profiles_must_be_disabled(tmp_path: Path) -> None:
    config = _minimal_config()
    generator_profile = cast(
        list[dict[str, Any]],
        config["models"]["generator_profiles"],
    )[0]
    generator_profile["enabled"] = True
    config_dir = _write_config_dir(tmp_path, config)

    with pytest.raises(ConfigValidationError) as exc_info:
        load_config_dir(config_dir)

    message = str(exc_info.value)
    assert "models.yaml" in message
    assert "external model profiles must set enabled=false" in message
