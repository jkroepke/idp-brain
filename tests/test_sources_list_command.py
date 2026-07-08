from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from idp_brain.cli import app

runner = CliRunner()
VALID_CONFIG = Path("tests/fixtures/config/sources_valid.yaml")
INVALID_CONFIG = Path("tests/fixtures/config/sources_invalid.yaml")


def test_sources_list_json_outputs_stable_metadata_only() -> None:
    result = runner.invoke(
        app,
        ["sources", "list", "--config", str(VALID_CONFIG), "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == [
        {
            "corpus_eligibility": "default_retrievable",
            "enabled": True,
            "extractor_profile": "docs_markdown_html",
            "license_policy": "allowed",
            "refresh_cadence": "manual",
            "sensitivity_class": "public",
            "source_id": "fixture-docs",
            "source_priority": 40,
            "source_type": "documentation_file",
            "tracked_refs": ["v1"],
            "version_strategy": "explicit_refs",
            "visibility_label": "public",
        },
        {
            "corpus_eligibility": "review_required",
            "enabled": False,
            "extractor_profile": "source_code",
            "license_policy": "review_required",
            "refresh_cadence": "daily",
            "sensitivity_class": "internal",
            "source_id": "fixture-local-tree",
            "source_priority": 30,
            "source_type": "local_directory",
            "tracked_refs": [],
            "version_strategy": "snapshot",
            "visibility_label": "invited_users",
        },
        {
            "corpus_eligibility": "review_required",
            "enabled": False,
            "extractor_profile": "docs_markdown_html",
            "license_policy": "review_required",
            "refresh_cadence": "manual",
            "sensitivity_class": "public",
            "source_id": "fixture-local-docs",
            "source_priority": 25,
            "source_type": "local_directory",
            "tracked_refs": ["local-snapshot"],
            "version_strategy": "snapshot",
            "visibility_label": "invited_users",
        },
    ]
    assert "local_path" not in result.output
    assert "url" not in result.output


def test_sources_list_table_outputs_human_metadata() -> None:
    result = runner.invoke(
        app,
        ["sources", "list", "--config", str(VALID_CONFIG), "--format", "table"],
    )

    assert result.exit_code == 0
    assert "source_id" in result.output
    assert "fixture-docs" in result.output
    assert "documentation_file" in result.output
    assert "default_retrievable" in result.output
    assert "fixture-local-tree" in result.output
    assert "snapshot" in result.output


def test_sources_list_rejects_invalid_sources_without_secret_values() -> None:
    result = runner.invoke(
        app,
        ["sources", "list", "--config", str(INVALID_CONFIG), "--format", "json"],
    )

    assert result.exit_code == 1
    assert "validation failed" in result.output
    assert "sources.0.source_type" in result.output
    assert "sources.0.corpus_eligibility" in result.output
    assert "private_wiki" not in result.output
    assert "super-secret-token" not in result.output
