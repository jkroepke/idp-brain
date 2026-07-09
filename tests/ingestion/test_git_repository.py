from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from idp_brain.ingestion.pipeline import run_ingestion
from idp_brain.models import Artifact, SourceChange, SourceVersion

from .conftest import run_git


def test_git_repository_ingestion_uses_local_deterministic_repo(
    monkeypatch: pytest.MonkeyPatch,
    ingestion_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    repository = _create_repository(tmp_path)
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.git_repository.GIT_CACHE_ROOT",
        tmp_path / "cache",
    )

    result = run_ingestion(
        config_path=_write_git_config(tmp_path, repository),
        source_id="ingestion-git",
        dry_run=False,
        session_factory=ingestion_session_factory,
    )[0]

    assert result.status == "completed"
    assert result.stats["discovered_artifacts"] == 4

    with ingestion_session_factory() as session:
        source_version = session.scalars(select(SourceVersion)).one()
        artifacts = session.scalars(select(Artifact).order_by(Artifact.path)).all()
        changes = session.scalars(select(SourceChange)).all()

    assert source_version.version_label.startswith("refs:")
    assert source_version.checksum is not None
    assert [artifact.path for artifact in artifacts] == ["README.md", "schema.json"]
    assert all(artifact.commit_sha is not None for artifact in artifacts)
    serialized_changes = json.dumps(
        [
            {
                "title": change.title,
                "commit_sha": change.commit_sha,
                "parent_shas": change.parent_shas,
            }
            for change in changes
        ],
        sort_keys=True,
    )
    assert "hunter2-ingestion" not in serialized_changes
    assert "sk-test-ingestion-secret" not in serialized_changes
    assert "[redacted]" in serialized_changes


def _create_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    repository.mkdir()
    run_git(repository, "init", "-b", "main")
    run_git(repository, "config", "user.name", "Fixture User")
    run_git(repository, "config", "user.email", "fixture@example.invalid")
    (repository / "README.md").write_text("# Git Fixture\n", encoding="utf-8")
    run_git(repository, "add", "README.md")
    run_git(repository, "commit", "-m", "initial safe commit")
    (repository / "schema.json").write_text('{"title":"Fixture"}\n', encoding="utf-8")
    run_git(repository, "add", "schema.json")
    run_git(repository, "commit", "-m", "rotate password hunter2-ingestion")
    run_git(repository, "tag", "v1.0.0")
    return repository


def _write_git_config(tmp_path: Path, repository: Path) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(
        f"""---
config_version: 1
kind: sources
sources:
  - source_id: ingestion-git
    source_type: git_repository
    url: {repository.as_posix()}
    tracked_refs:
      - main
      - v1.0.0
    version_strategy: explicit_refs
    include_paths:
      - "**/*.md"
      - "**/*.json"
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
