from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from idp_brain.ingestion.pipeline import run_ingestion
from idp_brain.models import Artifact, IngestionRun, SourceVersion

from .conftest import assert_no_forbidden_ingestion_text


def test_local_directory_ingestion_discovers_safe_artifact_metadata(
    monkeypatch: pytest.MonkeyPatch,
    ingestion_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    repository_root = Path.cwd()
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.local_directory.REPOSITORY_ROOT",
        repository_root,
    )
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.local_directory.FIXTURE_ALLOWLIST_ROOT",
        repository_root / "tests" / "fixtures" / "ingestion",
    )

    result = run_ingestion(
        config_path=_write_local_config(tmp_path),
        source_id="ingestion-local",
        dry_run=False,
        session_factory=ingestion_session_factory,
    )[0]

    assert result.status == "completed"
    assert result.stats["fetched_artifacts"] == 4
    assert result.stats["discovered_artifacts"] == 2
    assert result.stats["skipped_generated_files"] == 1
    assert result.stats["skipped_vendored_files"] == 1

    with ingestion_session_factory() as session:
        source_version = session.scalars(select(SourceVersion)).one()
        artifacts = session.scalars(select(Artifact).order_by(Artifact.path)).all()
        run = session.scalars(select(IngestionRun)).one()
        assert_no_forbidden_ingestion_text(session)

    assert source_version.is_current is True
    assert [artifact.path for artifact in artifacts] == ["data.json", "guide.md"]
    assert {artifact.corpus_eligibility_label for artifact in artifacts} == {
        "review_required"
    }
    assert all(artifact.sanitized_content_hash is None for artifact in artifacts)
    persisted = json.dumps(
        {
            "artifacts": [artifact.path for artifact in artifacts],
            "diagnostics": run.diagnostics,
        },
        sort_keys=True,
    )
    assert "sk-test-ingestion-secret" not in persisted
    assert "hunter2-ingestion" not in persisted


def _write_local_config(tmp_path: Path) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(
        """---
config_version: 1
kind: sources
sources:
  - source_id: ingestion-local
    source_type: local_directory
    local_path: tests/fixtures/ingestion/local
    tracked_refs:
      - local-snapshot
    version_strategy: snapshot
    include_paths:
      - "**/*.md"
      - "**/*.json"
      - "**/*.js"
      - "**/*.txt"
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
