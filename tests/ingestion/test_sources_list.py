from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from idp_brain.cli import app


def test_sources_list_exposes_metadata_without_fetch_details() -> None:
    result = CliRunner().invoke(
        app,
        [
            "sources",
            "list",
            "--config",
            "tests/fixtures/config/sources_valid.yaml",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert {source["source_id"] for source in payload} >= {
        "fixture-docs",
        "fixture-local-docs",
        "fixture-local-tree",
    }
    assert all("local_path" not in source for source in payload)
    assert all("repository_url" not in source for source in payload)
    assert all("visibility_label" in source for source in payload)
    assert all("corpus_eligibility" in source for source in payload)


def test_sources_list_validation_diagnostics_are_sanitized() -> None:
    result = CliRunner().invoke(
        app,
        [
            "sources",
            "list",
            "--config",
            str(Path("tests/fixtures/config/sources_invalid.yaml")),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 1
    assert "validation failed" in result.output
    assert "super-secret-token" not in result.output
    assert "private_wiki" not in result.output
