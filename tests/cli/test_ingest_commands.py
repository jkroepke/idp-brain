from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from idp_brain.cli import app
from idp_brain.config import load_sources_config
from idp_brain.ingestion.pipeline import IngestionRunResult, _select_sources
from idp_brain.ingestion.status import IngestionStatus

runner = CliRunner()


def result(source_id: str = "fixture") -> IngestionRunResult:
    return IngestionRunResult(
        run_id="run:1",
        source_id=source_id,
        status="completed",
        dry_run=True,
        stats={"changed_chunks": 2, "failed_artifacts": 0, "redacted_candidates": 1},
        requested_ref="v1",
        extractor_profile="docs",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
    )


def test_run_json_repeatable_filters_and_safe_defaults(monkeypatch) -> None:
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return [result("one"), result("two")]

    monkeypatch.setattr("idp_brain.cli.run_ingestion", fake)
    output = runner.invoke(
        app,
        [
            "ingest",
            "run",
            "--source-id",
            "one",
            "--source-id",
            "two",
            "--dry-run",
            "--json",
        ],
    )
    assert output.exit_code == 0
    assert seen["source_ids"] == ("one", "two")
    assert json.loads(output.output)[0]["validation_only"] is True


def test_run_rich_style_table_has_required_safe_columns(monkeypatch) -> None:
    monkeypatch.setattr("idp_brain.cli.run_ingestion", lambda **kwargs: [result()])
    output = runner.invoke(app, ["ingest", "run", "--dry-run"])
    assert output.exit_code == 0
    for heading in (
        "run_id",
        "source_id",
        "changed_chunks",
        "inactive_index_version",
        "validation_only",
    ):
        assert heading in output.output


def test_promote_fails_closed_before_orchestration(monkeypatch) -> None:
    called = False

    def fake(**kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("idp_brain.cli.run_ingestion", fake)
    output = runner.invoke(app, ["ingest", "run", "--promote"])
    assert output.exit_code == 1
    assert called is False


def test_status_json_filters_and_is_sanitized(monkeypatch) -> None:
    seen = {}
    row = IngestionStatus(
        run_id="run:1",
        source_id="fixture",
        version_ref="v1",
        profile="docs",
        status="failed",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        changed_chunk_count=0,
        failed_chunk_count=1,
        redacted_chunk_count=1,
    )

    def fake(**kwargs):
        seen.update(kwargs)
        return [row]

    monkeypatch.setattr("idp_brain.cli.ingestion_status", fake)
    output = runner.invoke(
        app, ["ingest", "status", "--source-id", "fixture", "--limit", "3", "--json"]
    )
    assert output.exit_code == 0
    assert seen["source_id"] == "fixture" and seen["limit"] == 3
    assert "hunter2" not in output.output


def test_secret_like_override_is_rejected_without_echoing_value() -> None:
    output = runner.invoke(app, ["ingest", "run", "--version", "password=hunter2"])
    assert output.exit_code != 0
    assert "hunter2" not in output.output


def test_operational_exception_is_fixed_and_unchained(monkeypatch) -> None:
    def fail(**kwargs):
        raise RuntimeError("password=hunter2 SELECT * /private/cache")

    monkeypatch.setattr("idp_brain.cli.run_ingestion", fail)
    output = runner.invoke(app, ["ingest", "run", "--dry-run"])
    assert output.exit_code == 1
    assert "Ingestion failed" in output.output
    for forbidden in ("hunter2", "SELECT", "/private", "RuntimeError"):
        assert forbidden not in output.output


def test_explicit_disabled_source_is_rejected_with_fixed_message() -> None:
    source = (
        load_sources_config(Path("config/sources.yaml"))
        .sources[0]
        .model_copy(update={"enabled": False})
    )
    with pytest.raises(ValueError, match="requested source is unavailable"):
        _select_sources([source], (source.source_id,))


def test_status_operational_exception_is_fixed_and_unchained(monkeypatch) -> None:
    def fail(**kwargs):
        raise RuntimeError("password=hunter2 SELECT /private/db")

    monkeypatch.setattr("idp_brain.cli.ingestion_status", fail)
    output = runner.invoke(app, ["ingest", "status", "--json"])
    assert output.exit_code == 1
    assert "Unable to read ingestion status" in output.output
    assert all(
        value not in output.output for value in ("hunter2", "SELECT", "/private")
    )


def test_run_result_strings_are_sanitized_in_json_and_table(monkeypatch) -> None:
    unsafe = result().model_copy() if hasattr(result(), "model_copy") else result()
    object.__setattr__(unsafe, "source_id", "password=hunter2\x00")
    object.__setattr__(unsafe, "requested_ref", "token=abc")
    monkeypatch.setattr("idp_brain.cli.run_ingestion", lambda **kwargs: [unsafe])
    for arguments in (
        ["ingest", "run", "--dry-run", "--json"],
        ["ingest", "run", "--dry-run"],
    ):
        output = runner.invoke(app, arguments)
        assert output.exit_code == 0
        assert "hunter2" not in output.output and "token=abc" not in output.output
