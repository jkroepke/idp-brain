from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from idp_brain.ingestion.pipeline import (
    IngestionStageNotImplementedError,
    run_ingestion,
)
from idp_brain.models import IngestionRun


def test_dry_run_records_completed_lifecycle(
    ingestion_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    result = run_ingestion(
        config_path=_write_documentation_config(tmp_path),
        source_id="documentation-only",
        dry_run=True,
        operator_label="pytest",
        session_factory=ingestion_session_factory,
    )[0]

    assert result.status == "completed"
    assert result.stats["fetched_artifacts"] == 0
    with ingestion_session_factory() as session:
        run = session.scalars(select(IngestionRun)).one()

    assert run.operator_label == "pytest"
    assert len(run.config_file_hash) == 64
    assert run.visibility_label == "invited_users"
    assert run.corpus_eligibility_label == "review_required"


def test_failed_run_diagnostics_do_not_leak_raw_exception_text(
    ingestion_session_factory: sessionmaker[Session],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    config_path = _write_documentation_config(tmp_path)

    with pytest.raises(IngestionStageNotImplementedError):
        run_ingestion(
            config_path=config_path,
            source_id="documentation-only",
            dry_run=False,
            session_factory=ingestion_session_factory,
        )

    with ingestion_session_factory() as session:
        run = session.scalars(select(IngestionRun)).one()

    assert run.status == "failed"
    assert run.error_message == "ingestion stage failed"
    diagnostics_text = str(run.diagnostics)
    assert "documentation-only" in diagnostics_text
    assert "raw diff --git a/private b/private" not in diagnostics_text
    assert "sk-test-ingestion-secret" not in diagnostics_text
    assert "raw diff --git a/private b/private" not in caplog.text


def _write_documentation_config(tmp_path: Path) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(
        """---
config_version: 1
kind: sources
sources:
  - source_id: documentation-only
    source_type: documentation_file
    tracked_refs:
      - v1
    version_strategy: explicit_refs
    include_paths:
      - "**/*.md"
    exclude_paths: []
    extractor_profile: docs_markdown_html
    source_priority: 10
    visibility_label: invited_users
    corpus_eligibility: review_required
    allowed_groups:
      - developers
    allowed_principals: []
    sensitivity_class: confidential
    license_policy: review_required
    refresh_cadence: manual
    enabled: true
""",
        encoding="utf-8",
    )
    return path
