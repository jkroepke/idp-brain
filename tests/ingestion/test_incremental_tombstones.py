from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from idp_brain.ingestion.pipeline import run_ingestion
from idp_brain.models import Artifact, ArtifactVersion


def test_incremental_ingestion_tombstones_removed_artifacts_idempotently(
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
        repository_root / "tests" / "fixtures" / "ingestion" / "changed",
    )

    first = _run_version(tmp_path, ingestion_session_factory, "v1")
    second = _run_version(tmp_path, ingestion_session_factory, "v2")
    third = _run_version(tmp_path, ingestion_session_factory, "v2")

    assert first.stats["added_artifacts"] == 3
    assert second.stats["changed_artifacts"] == 1
    assert second.stats["tombstoned_artifacts"] == 1
    assert second.stats["tombstoned_records"] == 1
    assert third.stats["unchanged_artifacts"] == 3
    assert third.stats["tombstoned_artifacts"] == 0
    assert third.stats["tombstoned_records"] == 0

    with ingestion_session_factory() as session:
        artifacts = {row.path: row for row in session.scalars(select(Artifact)).all()}
        versions = session.scalars(select(ArtifactVersion)).all()

    assert artifacts["removed.md"].source_version_id is None
    removed_versions = [
        version
        for version in versions
        if version.artifact_id == artifacts["removed.md"].id
    ]
    assert len(removed_versions) == 1
    assert removed_versions[0].is_current is False
    assert removed_versions[0].tombstoned_at is not None


def _run_version(
    tmp_path: Path,
    session_factory: sessionmaker[Session],
    version: str,
):
    return run_ingestion(
        config_path=_write_config(tmp_path, version),
        source_id="ingestion-incremental",
        dry_run=False,
        session_factory=session_factory,
    )[0]


def _write_config(tmp_path: Path, version: str) -> Path:
    path = tmp_path / f"sources-{version}.yaml"
    path.write_text(
        f"""---
config_version: 1
kind: sources
sources:
  - source_id: ingestion-incremental
    source_type: local_directory
    local_path: tests/fixtures/ingestion/changed/{version}
    tracked_refs:
      - local-snapshot
    version_strategy: snapshot
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
    sensitivity_class: internal
    license_policy: review_required
    refresh_cadence: manual
    enabled: true
""",
        encoding="utf-8",
    )
    return path
