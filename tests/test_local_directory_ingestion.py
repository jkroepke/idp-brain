from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from idp_brain.config import load_sources_config
from idp_brain.ingestion.fetchers import LocalDirectoryFetcher, LocalDirectoryPathError
from idp_brain.ingestion.pipeline import run_ingestion
from idp_brain.models import (
    Artifact,
    ArtifactVersion,
    Base,
    IngestionRun,
    Source,
    SourceVersion,
)
from idp_brain.repositories.source_versions import SourceVersionRepository

DEFAULT_CONFIG = Path("config/sources.yaml")
VALID_CONFIG = Path("tests/fixtures/config/sources_valid.yaml")
LOCAL_SOURCE_ID = "fixture-local-docs"
SECRET_CONTENT = "do-not-persist-this-secret-value"


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


def test_local_directory_ingestion_records_deterministic_artifacts(
    session_factory: sessionmaker[Session],
) -> None:
    first_results = run_ingestion(
        config_path=VALID_CONFIG,
        source_id=LOCAL_SOURCE_ID,
        dry_run=False,
        session_factory=session_factory,
    )
    second_results = run_ingestion(
        config_path=VALID_CONFIG,
        source_id=LOCAL_SOURCE_ID,
        dry_run=False,
        session_factory=session_factory,
    )

    assert first_results[0].status == "completed"
    assert first_results[0].stats["fetched_artifacts"] == 3
    assert first_results[0].stats["discovered_artifacts"] == 2
    assert second_results[0].stats["fetched_artifacts"] == 3
    assert second_results[0].stats["discovered_artifacts"] == 2
    assert first_results[0].stats["added_artifacts"] == 2
    assert second_results[0].stats["added_artifacts"] == 0
    assert second_results[0].stats["unchanged_artifacts"] == 2

    with session_factory() as session:
        source = session.scalars(select(Source)).one()
        source_versions = session.scalars(select(SourceVersion)).all()
        artifacts = session.scalars(select(Artifact).order_by(Artifact.path)).all()
        artifact_versions = session.scalars(select(ArtifactVersion)).all()
        runs = session.scalars(
            select(IngestionRun).order_by(IngestionRun.started_at)
        ).all()

    assert source.config_key == LOCAL_SOURCE_ID
    assert source.source_type == "local_directory"
    assert source.visibility_label == "invited_users"
    assert source.sensitivity_class == "public"
    assert source.license_policy_status == "review_required"

    assert len(source_versions) == 1
    source_version = source_versions[0]
    assert source_version.version_label.startswith("snapshot:")
    assert source_version.resolved_ref == "tests/fixtures/local_directory/docs"
    assert source_version.checksum is not None
    assert source_version.checksum.startswith("sha256:")
    assert source_version.is_current is True

    assert [artifact.path for artifact in artifacts] == ["index.md", "reference.json"]
    assert [artifact.logical_locator for artifact in artifacts] == [
        "fixture-local-docs:index.md",
        "fixture-local-docs:reference.json",
    ]
    assert {artifact.source_version_id for artifact in artifacts} == {
        source_version.id,
    }
    assert {artifact.visibility_label for artifact in artifacts} == {"invited_users"}
    assert {artifact.corpus_eligibility_label for artifact in artifacts} == {
        "review_required",
    }
    assert {artifact.sensitivity_class for artifact in artifacts} == {"public"}
    assert {artifact.license_policy_status for artifact in artifacts} == {
        "review_required",
    }
    assert all(artifact.checksum.startswith("sha256:") for artifact in artifacts)
    assert all(artifact.sanitized_content_hash is None for artifact in artifacts)
    assert len(artifact_versions) == 2

    assert len(runs) == 2
    assert {run.source_version_id for run in runs} == {source_version.id}
    assert runs[-1].diagnostics["source_version"] == source_version.version_label
    assert len(runs[-1].diagnostics["skipped_artifacts"]) == 1
    skipped = runs[-1].diagnostics["skipped_artifacts"][0]
    assert skipped["locator"] == "secret-example.txt"
    assert skipped["pattern"] == "**/*secret*"
    assert skipped["reason"] == "excluded_by_glob"
    assert skipped["included"] is False
    assert skipped["skipped"] is True
    assert skipped["discovery_rule_version"] == "artifact-discovery-v1"


def test_local_directory_ingestion_does_not_persist_secret_file_content(
    session_factory: sessionmaker[Session],
) -> None:
    run_ingestion(
        config_path=VALID_CONFIG,
        source_id=LOCAL_SOURCE_ID,
        dry_run=False,
        session_factory=session_factory,
    )

    with session_factory() as session:
        serialized = json.dumps(
            {
                "sources": [
                    _safe_model_dict(row) for row in session.scalars(select(Source))
                ],
                "versions": [
                    _safe_model_dict(row)
                    for row in session.scalars(select(SourceVersion))
                ],
                "artifacts": [
                    _safe_model_dict(row) for row in session.scalars(select(Artifact))
                ],
                "runs": [
                    _safe_model_dict(row)
                    for row in session.scalars(select(IngestionRun))
                ],
            },
            default=str,
            sort_keys=True,
        )

    assert SECRET_CONTENT not in serialized


def test_local_directory_sources_flush_with_schema_safe_labels(
    session_factory: sessionmaker[Session],
) -> None:
    local_directory_sources = []
    for config_path in (DEFAULT_CONFIG, VALID_CONFIG):
        local_directory_sources.extend(
            source
            for source in load_sources_config(config_path).sources
            if source.source_type == "local_directory"
        )

    assert local_directory_sources
    with session_factory() as session:
        repository = SourceVersionRepository(session)
        for source in local_directory_sources:
            repository.upsert_source(source)
        session.flush()


def test_changed_local_file_moves_current_version_flags(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    docs_root = repo_root / "local" / "docs"
    docs_root.mkdir(parents=True)
    config_path = repo_root / "sources.yaml"
    fixture_path = docs_root / "index.md"
    fixture_path.write_text("first safe snapshot\n", encoding="utf-8")
    config_path.write_text(
        """---
config_version: 1
kind: sources
sources:
  - source_id: mutable-local-docs
    source_type: local_directory
    local_path: local/docs
    tracked_refs:
      - local-snapshot
    version_strategy: snapshot
    include_paths:
      - "**/*.md"
    exclude_paths:
      - "**/*secret*"
    extractor_profile: docs_markdown_html
    source_priority: 25
    visibility_label: invited_users
    corpus_eligibility: review_required
    allowed_groups:
      - developers
    allowed_principals: []
    sensitivity_class: public
    license_policy: review_required
    refresh_cadence: manual
    enabled: true
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.local_directory.REPOSITORY_ROOT",
        repo_root,
    )
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.local_directory.FIXTURE_ALLOWLIST_ROOT",
        repo_root / "local",
    )

    first_result = run_ingestion(
        config_path=config_path,
        source_id="mutable-local-docs",
        dry_run=False,
        session_factory=session_factory,
    )[0]
    fixture_path.write_text("second safe snapshot\n", encoding="utf-8")
    second_result = run_ingestion(
        config_path=config_path,
        source_id="mutable-local-docs",
        dry_run=False,
        session_factory=session_factory,
    )[0]

    assert first_result.status == "completed"
    assert second_result.status == "completed"

    with session_factory() as session:
        source_versions = session.scalars(select(SourceVersion)).all()
        artifact = session.scalars(select(Artifact)).one()
        artifact_versions = session.scalars(select(ArtifactVersion)).all()

    assert len(source_versions) == 2
    current_source_version = next(
        version for version in source_versions if version.is_current
    )
    old_source_version = next(
        version for version in source_versions if not version.is_current
    )
    assert old_source_version.is_current is False
    assert current_source_version.is_current is True
    assert first_result.run_id != second_result.run_id

    assert len(artifact_versions) == 2
    current_artifact_version = next(
        version for version in artifact_versions if version.is_current
    )
    old_artifact_version = next(
        version for version in artifact_versions if not version.is_current
    )
    assert old_artifact_version.is_current is False
    assert current_artifact_version.is_current is True
    assert old_artifact_version.source_version_id == old_source_version.id
    assert current_artifact_version.source_version_id == current_source_version.id
    assert artifact.source_version_id == current_source_version.id
    assert artifact.first_containing_version_id == old_source_version.id
    assert artifact.last_containing_version_id == current_source_version.id
    assert current_artifact_version.first_containing_version_id == old_source_version.id
    assert current_artifact_version.last_containing_version_id == (
        current_source_version.id
    )


def test_excluded_local_artifact_is_retired(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    docs_root = repo_root / "local" / "docs"
    docs_root.mkdir(parents=True)
    (docs_root / "index.md").write_text("safe document\n", encoding="utf-8")
    config_path = repo_root / "sources.yaml"
    _write_mutable_local_config(config_path, exclude_paths=[])
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.local_directory.REPOSITORY_ROOT",
        repo_root,
    )
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.local_directory.FIXTURE_ALLOWLIST_ROOT",
        repo_root / "local",
    )

    first_result = run_ingestion(
        config_path=config_path,
        source_id="mutable-local-docs",
        dry_run=False,
        session_factory=session_factory,
    )[0]
    _write_mutable_local_config(config_path, exclude_paths=["index.md"])
    second_result = run_ingestion(
        config_path=config_path,
        source_id="mutable-local-docs",
        dry_run=False,
        session_factory=session_factory,
    )[0]

    assert first_result.stats["discovered_artifacts"] == 1
    assert second_result.stats["fetched_artifacts"] == 1
    assert second_result.stats["discovered_artifacts"] == 0

    with session_factory() as session:
        artifact = session.scalars(select(Artifact)).one()
        artifact_versions = session.scalars(select(ArtifactVersion)).all()
        latest_run = session.scalars(
            select(IngestionRun).order_by(IngestionRun.started_at)
        ).all()[-1]

    assert artifact.source_version_id is None
    assert [version.is_current for version in artifact_versions] == [False]
    assert latest_run.diagnostics["skipped_artifacts"][0]["reason"] == (
        "excluded_by_glob"
    )


def test_included_override_decisions_are_recorded_in_run_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    docs_root = repo_root / "local" / "docs"
    docs_root.mkdir(parents=True)
    (docs_root / "private.md").write_text("safe private fixture\n", encoding="utf-8")
    (docs_root / "client.generated.ts").write_text(
        "export const fixture = true;\n",
        encoding="utf-8",
    )
    config_path = repo_root / "sources.yaml"
    _write_mutable_local_config(
        config_path,
        include_paths=["**/*.md", "**/*.ts"],
        exclude_paths=["private.md"],
        include_generated=True,
        override_exclude_paths=["private.md"],
        discovery_override_reason="operator-approved-discovery-fixture",
    )
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.local_directory.REPOSITORY_ROOT",
        repo_root,
    )
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.local_directory.FIXTURE_ALLOWLIST_ROOT",
        repo_root / "local",
    )

    result = run_ingestion(
        config_path=config_path,
        source_id="mutable-local-docs",
        dry_run=False,
        session_factory=session_factory,
    )[0]

    assert result.status == "completed"
    assert result.stats["discovered_artifacts"] == 2
    with session_factory() as session:
        artifacts = session.scalars(select(Artifact).order_by(Artifact.path)).all()
        run = session.scalars(select(IngestionRun)).one()

    assert [artifact.path for artifact in artifacts] == [
        "client.generated.ts",
        "private.md",
    ]
    assert {artifact.corpus_eligibility_label for artifact in artifacts} == {
        "review_required"
    }
    assert next(
        artifact for artifact in artifacts if artifact.path == "client.generated.ts"
    ).is_generated
    included = run.diagnostics["included_artifacts"]
    assert {entry["locator"] for entry in included} == {
        "client.generated.ts",
        "private.md",
    }
    assert {entry["override_reason"] for entry in included} == {
        "operator-approved-discovery-fixture"
    }
    assert all(entry["included"] is True for entry in included)
    assert all(
        entry["discovery_rule_version"] == "artifact-discovery-v1" for entry in included
    )


def test_local_directory_fetcher_rejects_path_traversal() -> None:
    source = next(
        source
        for source in load_sources_config(VALID_CONFIG).sources
        if source.source_id == LOCAL_SOURCE_ID
    )
    unsafe_source = source.model_copy(update={"local_path": "../local_directory/docs"})

    with pytest.raises(LocalDirectoryPathError):
        LocalDirectoryFetcher(config_path=VALID_CONFIG).fetch(unsafe_source, run=None)  # type: ignore[arg-type]


def _safe_model_dict(row: object) -> dict[str, object]:
    return {
        key: value for key, value in vars(row).items() if not key.startswith("_sa_")
    }


def _write_mutable_local_config(
    config_path: Path,
    *,
    include_paths: list[str] | None = None,
    exclude_paths: list[str],
    include_generated: bool = False,
    override_exclude_paths: list[str] | None = None,
    discovery_override_reason: str | None = None,
) -> None:
    includes_yaml = "\n".join(
        f'      - "{path}"' for path in (include_paths or ["**/*.md"])
    )
    excludes_yaml = "\n".join(f'      - "{path}"' for path in exclude_paths)
    if not excludes_yaml:
        excludes_yaml = "      []"
    override_excludes = override_exclude_paths or []
    override_excludes_yaml = "\n".join(
        f'      - "{path}"' for path in override_excludes
    )
    if not override_excludes_yaml:
        override_excludes_yaml = "      []"
    override_reason_yaml = (
        f"    discovery_override_reason: {discovery_override_reason}\n"
        if discovery_override_reason is not None
        else ""
    )
    config_path.write_text(
        f"""---
config_version: 1
kind: sources
sources:
  - source_id: mutable-local-docs
    source_type: local_directory
    local_path: local/docs
    tracked_refs:
      - local-snapshot
    version_strategy: snapshot
    include_paths:
{includes_yaml}
    exclude_paths:
{excludes_yaml}
    extractor_profile: docs_markdown_html
    include_generated: {str(include_generated).lower()}
    override_exclude_paths:
{override_excludes_yaml}
{override_reason_yaml}    include_vendored: false
    source_priority: 25
    visibility_label: invited_users
    corpus_eligibility: review_required
    allowed_groups:
      - developers
    allowed_principals: []
    sensitivity_class: public
    license_policy: review_required
    refresh_cadence: manual
    enabled: true
""",
        encoding="utf-8",
    )
