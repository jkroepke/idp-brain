from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from idp_brain.ingestion.pipeline import run_ingestion
from idp_brain.models import (
    Artifact,
    ArtifactVersion,
    Base,
    ChangeVersion,
    IngestionRun,
    Source,
    SourceChange,
    SourceVersion,
)


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


def test_git_repository_ingestion_records_refs_artifacts_and_changes(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "cache" / "git"
    repository = _create_fixture_repository(tmp_path)
    config_path = _write_git_sources_config(tmp_path, repository)
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.git_repository.GIT_CACHE_ROOT",
        cache_root,
    )

    result = run_ingestion(
        config_path=config_path,
        source_id="fixture-git-repo",
        dry_run=False,
        session_factory=session_factory,
    )[0]

    assert result.status == "completed"
    assert result.stats["fetched_artifacts"] == 2
    assert result.stats["discovered_artifacts"] == 2
    assert cache_root.is_dir()

    with session_factory() as session:
        source = session.scalars(select(Source)).one()
        source_version = session.scalars(select(SourceVersion)).one()
        artifacts = session.scalars(select(Artifact).order_by(Artifact.path)).all()
        artifact_versions = session.scalars(select(ArtifactVersion)).all()
        changes = session.scalars(
            select(SourceChange).order_by(SourceChange.authored_at)
        ).all()
        change_versions = session.scalars(select(ChangeVersion)).all()
        run = session.scalars(select(IngestionRun)).one()

    assert source.config_key == "fixture-git-repo"
    assert source.source_type == "git_repository"
    assert source.repository_url == str(repository)
    assert source.visibility_label == "invited_users"

    assert source_version.version_label.startswith("branch:main@")
    assert source_version.branch == "main"
    assert source_version.tag is None
    assert source_version.commit_sha is not None
    assert len(source_version.commit_sha) == 40
    assert source_version.resolved_ref == source_version.commit_sha
    assert source_version.repository_url == str(repository)
    assert source_version.is_current is True

    assert [artifact.path for artifact in artifacts] == ["README.md", "schema.json"]
    assert {artifact.commit_sha for artifact in artifacts} == {
        source_version.commit_sha,
    }
    assert {artifact.visibility_label for artifact in artifacts} == {"invited_users"}
    assert all(artifact.checksum.startswith("gitblob:") for artifact in artifacts)
    assert all(artifact.sanitized_content_hash is None for artifact in artifacts)
    assert len(artifact_versions) == 2
    assert {version.commit_sha for version in artifact_versions} == {
        source_version.commit_sha,
    }
    assert {artifact.first_containing_version_id for artifact in artifacts} == {None}
    assert {artifact.last_containing_version_id for artifact in artifacts} == {None}
    assert {version.first_containing_version_id for version in artifact_versions} == {
        None
    }
    assert {version.last_containing_version_id for version in artifact_versions} == {
        None
    }

    assert len(changes) == 2
    assert len(change_versions) == 2
    assert {change.source_version_id for change in changes} == {source_version.id}
    assert {change.visibility_label for change in changes} == {"invited_users"}
    assert changes[0].parent_shas == []
    assert changes[1].parent_shas == [changes[0].commit_sha]
    serialized_changes = json.dumps(
        [_safe_model_dict(change) for change in changes],
        default=str,
        sort_keys=True,
    )
    assert "password" not in serialized_changes
    assert "hunter2" not in serialized_changes
    assert "secret" not in serialized_changes
    assert "abc123" not in serialized_changes
    assert "[redacted]" in serialized_changes
    assert run.source_version_id == source_version.id
    assert run.diagnostics["source_version"] == source_version.version_label


def test_file_url_git_repository_ingestion_uses_same_fetch_path(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "cache" / "git"
    repository = _create_fixture_repository(tmp_path)
    config_path = _write_git_sources_config(tmp_path, repository, file_url=True)
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.git_repository.GIT_CACHE_ROOT",
        cache_root,
    )

    result = run_ingestion(
        config_path=config_path,
        source_id="fixture-git-repo",
        dry_run=False,
        session_factory=session_factory,
    )[0]

    assert result.status == "completed"
    with session_factory() as session:
        source_version = session.scalars(select(SourceVersion)).one()
        artifacts = session.scalars(select(Artifact)).all()
    assert source_version.commit_sha is not None
    assert len(artifacts) == 2


def test_git_repository_cache_is_recreated_when_url_changes(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "cache" / "git"
    first_repository = _create_single_file_repository(
        tmp_path,
        "first-repository",
        "first.md",
        "First safe document\n",
    )
    second_repository = _create_single_file_repository(
        tmp_path,
        "second-repository",
        "second.md",
        "Second safe document\n",
    )
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.git_repository.GIT_CACHE_ROOT",
        cache_root,
    )

    run_ingestion(
        config_path=_write_git_sources_config(
            tmp_path,
            first_repository,
            include_paths=["first.md", "second.md"],
        ),
        source_id="fixture-git-repo",
        dry_run=False,
        session_factory=session_factory,
    )
    run_ingestion(
        config_path=_write_git_sources_config(
            tmp_path,
            second_repository,
            include_paths=["first.md", "second.md"],
        ),
        source_id="fixture-git-repo",
        dry_run=False,
        session_factory=session_factory,
    )

    with session_factory() as session:
        source = session.scalars(select(Source)).one()
        current_source_version = session.scalars(
            select(SourceVersion).where(SourceVersion.is_current.is_(True))
        ).one()
        artifacts = session.scalars(select(Artifact).order_by(Artifact.path)).all()
        artifact_versions = session.scalars(
            select(ArtifactVersion).order_by(ArtifactVersion.artifact_id)
        ).all()

    assert source.repository_url == str(second_repository)
    assert current_source_version.repository_url == str(second_repository)
    assert [artifact.path for artifact in artifacts] == ["first.md", "second.md"]
    current_artifact = next(
        artifact for artifact in artifacts if artifact.path == "second.md"
    )
    stale_artifact = next(
        artifact for artifact in artifacts if artifact.path == "first.md"
    )
    assert current_artifact.source_version_id == current_source_version.id
    assert stale_artifact.source_version_id is None
    assert [
        version.is_current
        for version in artifact_versions
        if version.artifact_id == current_artifact.id
    ] == [True]
    assert [
        version.is_current
        for version in artifact_versions
        if version.artifact_id == stale_artifact.id
    ] == [False]


def test_git_repository_ingestion_resolves_all_tracked_refs(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "cache" / "git"
    repository = _create_fixture_repository(tmp_path)
    config_path = _write_git_sources_config(
        tmp_path,
        repository,
        tracked_refs=["main", "side"],
        include_paths=["README.md", "schema.json", "side.md"],
    )
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.git_repository.GIT_CACHE_ROOT",
        cache_root,
    )

    result = run_ingestion(
        config_path=config_path,
        source_id="fixture-git-repo",
        dry_run=False,
        session_factory=session_factory,
    )[0]

    with session_factory() as session:
        source_version = session.scalars(select(SourceVersion)).one()
        artifacts = session.scalars(select(Artifact).order_by(Artifact.path)).all()
        changes = session.scalars(select(SourceChange)).all()

    assert result.status == "completed"
    assert source_version.version_label.startswith("refs:")
    assert source_version.commit_sha is None
    assert source_version.branch is None
    assert {artifact.path for artifact in artifacts} == {
        "README.md",
        "schema.json",
        "side.md",
    }
    assert len(changes) == 3


def _create_fixture_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "remote-repository"
    repository.mkdir()
    fixture_root = Path("tests/fixtures/git_repository")
    shutil.copy(fixture_root / "README.md", repository / "README.md")
    _git(repository, "init")
    _git(repository, "config", "user.name", "IDP Brain CI")
    _git(repository, "config", "user.email", "ci@example.invalid")
    _git(repository, "add", "README.md")
    _git(
        repository,
        "commit",
        "-m",
        "password is hunter2",
        date="2024-01-01T00:00:00+00:00",
    )
    _git(repository, "branch", "side")
    shutil.copy(fixture_root / "schema.json", repository / "schema.json")
    _git(repository, "add", "schema.json")
    _git(
        repository,
        "commit",
        "-m",
        "secret=abc123",
        date="2024-01-02T00:00:00+00:00",
    )
    _git(repository, "branch", "-M", "main")
    _git(repository, "switch", "side")
    (repository / "side.md").write_text("Side branch document\n", encoding="utf-8")
    _git(repository, "add", "side.md")
    _git(
        repository,
        "commit",
        "-m",
        "Add side branch document",
        date="2024-01-03T00:00:00+00:00",
    )
    _git(repository, "switch", "main")
    return repository


def _write_git_sources_config(
    tmp_path: Path,
    repository: Path,
    *,
    file_url: bool = False,
    tracked_refs: list[str] | None = None,
    include_paths: list[str] | None = None,
) -> Path:
    repository_url = repository.as_uri() if file_url else str(repository)
    refs_yaml = "\n".join(f"      - {ref}" for ref in (tracked_refs or ["main"]))
    includes_yaml = "\n".join(
        f"      - {path}" for path in (include_paths or ["README.md", "schema.json"])
    )
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        f"""---
config_version: 1
kind: sources
sources:
  - source_id: fixture-git-repo
    source_type: git_repository
    url: {repository_url}
    tracked_refs:
{refs_yaml}
    version_strategy: explicit_refs
    include_paths:
{includes_yaml}
    exclude_paths:
      - "**/*private*"
    extractor_profile: source_code
    source_priority: 25
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
    return config_path


def _create_single_file_repository(
    tmp_path: Path,
    repository_name: str,
    path: str,
    content: str,
) -> Path:
    repository = tmp_path / repository_name
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.name", "IDP Brain CI")
    _git(repository, "config", "user.email", "ci@example.invalid")
    (repository / path).write_text(content, encoding="utf-8")
    _git(repository, "add", path)
    _git(
        repository,
        "commit",
        "-m",
        f"Add {path}",
        date="2024-01-01T00:00:00+00:00",
    )
    _git(repository, "branch", "-M", "main")
    return repository


def _git(
    repository: Path,
    *args: str,
    date: str | None = None,
) -> None:
    env = os.environ.copy()
    if date is not None:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )


def _safe_model_dict(row: object) -> dict[str, object]:
    return {
        key: value for key, value in vars(row).items() if not key.startswith("_sa_")
    }
