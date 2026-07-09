"""Migration-backed ingestion regressions.

The composition test in this module intentionally invokes extraction, redaction,
chunking, and repository persistence manually after public ingestion has recorded
source/artifact metadata. It verifies those stage contracts against the migrated
Postgres schema; it does not claim product ingestion wires those stages yet.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, sessionmaker

from idp_brain.config import load_security_config
from idp_brain.config.models import ExtractorProfileConfig
from idp_brain.ingestion.chunking import ChunkingPipeline
from idp_brain.ingestion.extractors import ArtifactExtractionContext, MarkdownExtractor
from idp_brain.ingestion.pipeline import run_ingestion
from idp_brain.ingestion.redaction_stage import RedactionStage
from idp_brain.models import Artifact, Chunk, Citation
from idp_brain.repositories import (
    ArtifactExtractionRepository,
    ChunkRepository,
    CitationRepository,
)

from .conftest import assert_no_forbidden_ingestion_text

pytestmark = pytest.mark.integration


def test_ingestion_suite_database_fixture_rebuilds_schema(
    migrated_postgres_engine,
) -> None:
    inspector = inspect(migrated_postgres_engine)
    tables = set(inspector.get_table_names())

    assert {
        "sources",
        "source_versions",
        "artifacts",
        "artifact_versions",
        "artifact_extractions",
        "redaction_events",
        "chunks",
        "chunk_versions",
        "citations",
        "ingestion_runs",
    } <= tables


def test_local_directory_ingestion_runs_on_migrated_postgres_schema(
    monkeypatch: pytest.MonkeyPatch,
    migrated_postgres_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    _allow_ingestion_fixtures(monkeypatch)

    result = run_ingestion(
        config_path=_write_local_config(tmp_path, "postgres-local"),
        source_id="postgres-local",
        dry_run=False,
        session_factory=migrated_postgres_session_factory,
    )[0]

    with migrated_postgres_session_factory() as session:
        artifacts = session.scalars(select(Artifact).order_by(Artifact.path)).all()
        chunks = session.scalars(select(Chunk)).all()
        citations = session.scalars(select(Citation)).all()
        assert_no_forbidden_ingestion_text(session)

    assert result.status == "completed"
    assert result.stats["fetched_artifacts"] == 4
    assert result.stats["discovered_artifacts"] == 2
    assert [artifact.path for artifact in artifacts] == ["data.json", "guide.md"]
    assert chunks == []
    assert citations == []


def test_manual_sanitized_stage_composition_runs_on_migrated_postgres_schema(
    monkeypatch: pytest.MonkeyPatch,
    migrated_postgres_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    _allow_ingestion_fixtures(monkeypatch)
    result = run_ingestion(
        config_path=_write_local_config(tmp_path, "postgres-composition"),
        source_id="postgres-composition",
        dry_run=False,
        session_factory=migrated_postgres_session_factory,
    )[0]

    with migrated_postgres_session_factory() as session:
        artifact = session.scalars(
            select(Artifact).where(Artifact.path == "guide.md")
        ).one()
        artifact_id = artifact.id
        source_version_id = artifact.source_version_id

    extraction = MarkdownExtractor().extract(
        ArtifactExtractionContext(
            artifact_id=artifact_id,
            source_id="source:postgres-composition",
            source_version_id=source_version_id,
            path="guide.md",
            logical_locator="fixture:guide.md",
            source_type="local_directory",
            artifact_role="documentation",
            language=None,
            extractor_profile="ingestion_docs",
            visibility_label="invited_users",
            sensitivity_class="confidential",
            license_policy_label="review_required",
            corpus_eligibility_label="review_required",
        ),
        Path("tests/fixtures/ingestion/local/guide.md").read_bytes(),
    )
    redacted = RedactionStage(
        load_security_config(Path("config/security.yaml"))
    ).redact(extraction)
    chunking = ChunkingPipeline(_extractor_profile()).chunk_result(redacted)

    with migrated_postgres_session_factory() as session:
        extraction_row = ArtifactExtractionRepository(
            session
        ).create_from_sanitized_result(redacted, ingestion_run_id=result.run_id)
        chunk_repository = ChunkRepository(session)
        citation_repository = CitationRepository(session)
        for chunk, citation in zip(chunking.chunks, chunking.citations, strict=True):
            chunk = replace(chunk, extraction_id=extraction_row.id)
            chunk_row = chunk_repository.upsert_chunk(chunk)
            chunk_repository.upsert_chunk_version(chunk_row=chunk_row)
            citation_repository.upsert_citation(citation, chunk_id=chunk_row.id)
        session.commit()

        chunks = session.scalars(select(Chunk)).all()
        citations = session.scalars(select(Citation)).all()
        assert_no_forbidden_ingestion_text(session)

    assert chunks
    assert citations
    assert all(chunk.extraction_id == extraction_row.id for chunk in chunks)
    assert all(chunk.source_id == "source:postgres-composition" for chunk in chunks)
    assert all(chunk.sanitized_content_hash for chunk in chunks)
    assert all(citation.sanitized_content_hash for citation in citations)


def _allow_ingestion_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    repository_root = Path.cwd()
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.local_directory.REPOSITORY_ROOT",
        repository_root,
    )
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.local_directory.FIXTURE_ALLOWLIST_ROOT",
        repository_root / "tests" / "fixtures" / "ingestion",
    )


def _write_local_config(tmp_path: Path, source_id: str) -> Path:
    path = tmp_path / f"{source_id}.yaml"
    path.write_text(
        f"""---
config_version: 1
kind: sources
sources:
  - source_id: {source_id}
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


def _extractor_profile() -> ExtractorProfileConfig:
    return ExtractorProfileConfig.model_validate(
        {
            "profile_id": "ingestion_docs",
            "family": "docs",
            "enabled": True,
            "file_patterns": ["**/*"],
            "include_generated": False,
            "include_vendored": False,
            "tools": [
                {
                    "tool_id": "builtin-ingestion",
                    "enabled": True,
                    "command": [],
                    "options": {
                        "chunk_size_chars": 500,
                        "chunk_overlap_chars": 50,
                    },
                }
            ],
            "validator_commands": [],
            "fallback_profile": None,
        }
    )
