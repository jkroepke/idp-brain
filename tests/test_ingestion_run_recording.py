from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from typer.testing import CliRunner

from idp_brain.cli import app
from idp_brain.ingestion.pipeline import (
    IngestionStageNotImplementedError,
    run_ingestion,
)
from idp_brain.models import Base, IngestionRun, empty_ingestion_counters

VALID_CONFIG = Path("tests/fixtures/config/sources_valid.yaml")
SECRET_VALUE = "super-secret-token"


@pytest.fixture()
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory: sessionmaker[Session] = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    yield factory
    engine.dispose()


def test_dry_run_records_started_run_before_source_work(
    session_factory: sessionmaker[Session],
) -> None:
    observed_statuses: list[str] = []

    def assert_run_is_durable(run: IngestionRun) -> None:
        with session_factory() as session:
            recorded = session.get(IngestionRun, run.id)
            assert recorded is not None
            observed_statuses.append(recorded.status)

    results = run_ingestion(
        config_path=VALID_CONFIG,
        source_id="fixture-docs",
        dry_run=True,
        operator_label="pytest",
        session_factory=session_factory,
        before_source_work=assert_run_is_durable,
    )

    assert observed_statuses == ["started"]
    assert len(results) == 1
    assert results[0].source_id == "fixture-docs"
    assert results[0].status == "completed"
    assert results[0].stats == empty_ingestion_counters()

    with session_factory() as session:
        run = session.scalars(select(IngestionRun)).one()
        assert run.source_id is None
        assert run.config_source_id == "fixture-docs"
        assert run.requested_ref == "v1"
        assert run.config_file_hash is not None
        assert len(run.config_file_hash) == 64
        assert run.operator_label == "pytest"
        assert run.extractor_profile == "docs_markdown_html"
        assert run.visibility_label == "public"
        assert run.sensitivity_class == "public"
        assert run.license_policy_status == "allowed"
        assert run.corpus_eligibility_label == "default_retrievable"
        assert run.status == "completed"
        assert run.completed_at is not None
        assert run.diagnostics == {}


def test_all_enabled_sources_dry_run_skips_disabled_sources(
    session_factory: sessionmaker[Session],
) -> None:
    results = run_ingestion(
        config_path=VALID_CONFIG,
        source_id=None,
        dry_run=True,
        session_factory=session_factory,
    )

    assert [result.source_id for result in results] == ["fixture-docs"]
    with session_factory() as session:
        assert session.scalars(select(IngestionRun.config_source_id)).all() == [
            "fixture-docs"
        ]


def test_failure_marks_existing_run_failed_without_secret_diagnostics(
    session_factory: sessionmaker[Session],
) -> None:
    def fail_after_started(_: IngestionRun) -> None:
        raise RuntimeError(f"failed with {SECRET_VALUE}")

    with pytest.raises(RuntimeError):
        run_ingestion(
            config_path=VALID_CONFIG,
            source_id="fixture-docs",
            dry_run=True,
            session_factory=session_factory,
            before_source_work=fail_after_started,
        )

    with session_factory() as session:
        run = session.scalars(select(IngestionRun)).one()
        assert run.status == "failed"
        assert run.error_message == "ingestion stage failed"
        assert run.completed_at is not None
        serialized = json.dumps(run.diagnostics, sort_keys=True)
        assert "RuntimeError" in serialized
        assert "started" in serialized
        assert SECRET_VALUE not in serialized
        assert SECRET_VALUE not in (run.error_message or "")


def test_non_dry_run_placeholder_failure_is_persisted_and_raised(
    session_factory: sessionmaker[Session],
) -> None:
    with pytest.raises(IngestionStageNotImplementedError):
        run_ingestion(
            config_path=VALID_CONFIG,
            source_id="fixture-docs",
            dry_run=False,
            session_factory=session_factory,
        )

    with session_factory() as session:
        run = session.scalars(select(IngestionRun)).one()
        assert run.status == "failed"
        assert run.error_message == "ingestion stage failed"
        assert run.diagnostics["error_type"] == "IngestionStageNotImplementedError"
        assert run.diagnostics["stage"] == "started"


def test_ingest_run_cli_outputs_dry_run_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_ingestion(**_: object) -> list[object]:
        class Result:
            run_id = "run-1"
            source_id = "fixture-docs"
            status = "completed"
            dry_run = True
            stats = empty_ingestion_counters()

            def to_dict(self) -> dict[str, object]:
                return {
                    "run_id": self.run_id,
                    "source_id": self.source_id,
                    "status": self.status,
                    "dry_run": self.dry_run,
                    "stats": self.stats,
                }

        return [Result()]

    monkeypatch.setattr("idp_brain.cli.run_ingestion", fake_run_ingestion)
    result = CliRunner().invoke(
        app,
        [
            "ingest",
            "run",
            "--source",
            "fixture-docs",
            "--config",
            str(VALID_CONFIG),
            "--dry-run",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)[0]["status"] == "completed"


def test_ingest_run_cli_exits_one_when_non_dry_run_stage_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_ingestion(**_: object) -> list[object]:
        raise IngestionStageNotImplementedError(
            "source fetching is implemented in later MVP steps"
        )

    monkeypatch.setattr("idp_brain.cli.run_ingestion", fake_run_ingestion)
    result = CliRunner().invoke(
        app,
        [
            "ingest",
            "run",
            "--source",
            "fixture-docs",
            "--config",
            str(VALID_CONFIG),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 1
    assert "source fetching is implemented in later MVP steps" in result.output
