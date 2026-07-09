from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from idp_brain.ingestion.chunking import SanitizedChunk
from idp_brain.ingestion.pipeline import run_ingestion
from idp_brain.ingestion.tombstones import (
    ARTIFACT_REMOVED_FROM_SOURCE,
    CHUNK_REMOVED_FROM_SOURCE,
)
from idp_brain.models import (
    Artifact,
    ArtifactVersion,
    Base,
    Chunk,
    ChunkVersion,
    IngestionRun,
    Source,
    SourceVersion,
)
from idp_brain.repositories import ChunkRepository


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


def test_local_ingestion_records_incremental_artifact_decisions(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    repository_root = Path.cwd()
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.local_directory.REPOSITORY_ROOT",
        repository_root,
    )
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.local_directory.FIXTURE_ALLOWLIST_ROOT",
        repository_root / "tests" / "fixtures" / "incremental",
    )

    first = run_ingestion(
        config_path=_write_incremental_config(tmp_path, "v1"),
        source_id="incremental-local",
        dry_run=False,
        session_factory=session_factory,
    )[0]
    second = run_ingestion(
        config_path=_write_incremental_config(tmp_path, "v2"),
        source_id="incremental-local",
        dry_run=False,
        session_factory=session_factory,
    )[0]
    third = run_ingestion(
        config_path=_write_incremental_config(tmp_path, "v2"),
        source_id="incremental-local",
        dry_run=False,
        session_factory=session_factory,
    )[0]

    assert first.status == "completed"
    assert first.stats["added_artifacts"] == 3
    assert first.stats["changed_artifacts"] == 0
    assert first.stats["unchanged_artifacts"] == 0
    assert first.stats["tombstoned_artifacts"] == 0

    assert second.status == "completed"
    assert second.stats["added_artifacts"] == 1
    assert second.stats["changed_artifacts"] == 1
    assert second.stats["unchanged_artifacts"] == 1
    assert second.stats["tombstoned_artifacts"] == 1
    assert second.stats["tombstoned_records"] == 1
    assert third.status == "completed"
    assert third.stats["added_artifacts"] == 0
    assert third.stats["changed_artifacts"] == 0
    assert third.stats["unchanged_artifacts"] == 3
    assert third.stats["tombstoned_artifacts"] == 0
    assert third.stats["tombstoned_records"] == 0

    with session_factory() as session:
        source_versions = session.scalars(
            select(SourceVersion).order_by(SourceVersion.version_label)
        ).all()
        artifacts = {
            artifact.path: artifact
            for artifact in session.scalars(select(Artifact)).all()
        }
        artifact_versions = session.scalars(select(ArtifactVersion)).all()
        second_run = session.get(IngestionRun, second.run_id)
        third_run = session.get(IngestionRun, third.run_id)

    assert len(source_versions) == 2
    assert second_run is not None
    assert third_run is not None
    assert set(artifacts) == {"added.md", "changed.md", "removed.md", "stable.md"}
    assert artifacts["removed.md"].source_version_id is None
    assert artifacts["stable.md"].source_version_id is not None
    assert artifacts["changed.md"].source_version_id is not None
    assert artifacts["added.md"].source_version_id is not None

    removed_versions = [
        version
        for version in artifact_versions
        if version.artifact_id == artifacts["removed.md"].id
    ]
    stable_versions = [
        version
        for version in artifact_versions
        if version.artifact_id == artifacts["stable.md"].id
    ]
    assert len(removed_versions) == 1
    assert removed_versions[0].is_current is False
    assert removed_versions[0].tombstoned_at is not None
    assert removed_versions[0].tombstone_reason == ARTIFACT_REMOVED_FROM_SOURCE
    assert len(stable_versions) == 2
    assert sum(version.is_current for version in stable_versions) == 1
    assert {version.tombstone_reason for version in stable_versions} == {None}

    diagnostics = second_run.diagnostics
    assert {item["status"] for item in diagnostics["incremental_artifacts"]} == {
        "added",
        "changed",
        "unchanged",
        "tombstoned",
    }
    assert "removed document is removed" not in str(diagnostics).lower()
    assert {
        item["status"] for item in third_run.diagnostics["incremental_artifacts"]
    } == {"unchanged"}


def test_chunk_versions_are_reused_and_tombstoned_without_deleting_history(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        _add_chunk_graph(session)
        repository = ChunkRepository(session)
        stable_v1 = repository.upsert_chunk(_chunk("stable", "source-version:v1"))
        removed_v1 = repository.upsert_chunk(_chunk("removed", "source-version:v1"))
        repository.upsert_chunk_version(chunk_row=stable_v1)
        repository.upsert_chunk_version(chunk_row=removed_v1)
        session.commit()

        stable_v2 = repository.upsert_chunk(
            replace(
                _chunk("stable", "source-version:v1"),
                source_version_id="source-version:v2",
            )
        )
        repository.upsert_chunk_version(chunk_row=stable_v2)
        tombstoned = repository.retire_chunks_absent_from_snapshot(
            source_id="source:incremental",
            current_chunk_keys={stable_v2.chunk_key},
        )
        repeated_tombstoned = repository.retire_chunks_absent_from_snapshot(
            source_id="source:incremental",
            current_chunk_keys={stable_v2.chunk_key},
        )
        session.commit()

        chunks = session.scalars(select(Chunk).order_by(Chunk.chunk_key)).all()
        chunk_versions = session.scalars(
            select(ChunkVersion).order_by(ChunkVersion.chunk_id)
        ).all()

    assert tombstoned == 1
    assert repeated_tombstoned == 0
    assert [chunk.chunk_key for chunk in chunks] == ["chunk:removed", "chunk:stable"]
    assert (
        next(chunk for chunk in chunks if chunk.id == "chunk:removed").source_version_id
        is None
    )
    assert (
        next(chunk for chunk in chunks if chunk.id == "chunk:stable").source_version_id
        == "source-version:v2"
    )

    removed_versions = [
        version for version in chunk_versions if version.chunk_id == "chunk:removed"
    ]
    stable_versions = [
        version for version in chunk_versions if version.chunk_id == "chunk:stable"
    ]
    assert len(removed_versions) == 1
    assert removed_versions[0].is_current is False
    assert removed_versions[0].tombstoned_at is not None
    assert removed_versions[0].tombstone_reason == CHUNK_REMOVED_FROM_SOURCE
    assert removed_versions[0].checksum == "sha256:removed"
    assert len(stable_versions) == 2
    assert sum(version.is_current for version in stable_versions) == 1
    assert {version.checksum for version in stable_versions} == {"sha256:stable"}


def _write_incremental_config(tmp_path: Path, fixture_version: str) -> Path:
    config_path = tmp_path / f"sources-{fixture_version}.yaml"
    config_path.write_text(
        f"""---
config_version: 1
kind: sources
sources:
  - source_id: incremental-local
    source_type: local_directory
    local_path: tests/fixtures/incremental/{fixture_version}
    tracked_refs:
      - local-snapshot
    version_strategy: snapshot
    include_paths:
      - "**/*.md"
    exclude_paths: []
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
    return config_path


def _add_chunk_graph(session: Session) -> None:
    source = Source(
        id="source:incremental",
        config_key="incremental-local",
        name="incremental-local",
        source_type="local_directory",
        visibility_label="invited_users",
        sensitivity_class="public",
        license_policy_status="review_required",
    )
    session.add(source)
    for label in ("v1", "v2"):
        session.add(
            SourceVersion(
                id=f"source-version:{label}",
                source_id=source.id,
                version_label=label,
                source_allowlisted=False,
                visibility_label="invited_users",
                sensitivity_class="public",
                license_policy_status="review_required",
                redaction_status="redacted",
            )
        )
    session.add(
        Artifact(
            id="artifact:doc",
            artifact_key="doc.md",
            artifact_type="document",
            source_id=source.id,
            source_version_id="source-version:v1",
            path="doc.md",
            logical_locator="incremental-local:doc.md",
            source_type="local_directory",
            source_allowlisted=False,
            visibility_label="invited_users",
            sensitivity_class="public",
            license_policy_status="review_required",
            redaction_status="redacted",
            corpus_eligibility_label="review_required",
        )
    )
    session.flush()


def _chunk(name: str, source_version_id: str) -> SanitizedChunk:
    return SanitizedChunk(
        chunk_key=f"chunk:{name}",
        artifact_id="artifact:doc",
        extraction_id=None,
        source_id="source:incremental",
        source_version_id=source_version_id,
        source_type="local_directory",
        source_url=f"incremental-local:{name}.md",
        artifact_path="doc.md",
        logical_locator=f"incremental-local:{name}.md",
        sanitized_text=f"safe {name} text",
        sanitized_content_hash=f"sha256:{name}",
        heading_path=None,
        structure_path=(name,),
        symbol_path=None,
        signature_text=None,
        language="markdown",
        artifact_role="documentation",
        chunk_kind="document_text",
        chunker_profile="docs-v1",
        token_count=3,
        redaction_status="redacted",
        source_allowlisted=False,
        visibility_label="invited_users",
        sensitivity_class="public",
        corpus_eligibility_label="review_required",
        license_policy_label="review_required",
        license_id=None,
    )
