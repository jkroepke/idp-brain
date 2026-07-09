"""Public ingestion assertions plus explicit manual stage-composition regressions.

These tests must not imply that product ingestion currently orchestrates extraction,
redaction, chunking, or citation persistence. The public path assertion below locks
the current behavior: `run_ingestion()` stops after fetch/discovery persistence.
The composition test manually invokes later stage contracts to protect their
persistence boundaries until a future MVP step wires them into product ingestion.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from idp_brain.config import load_security_config
from idp_brain.config.models import ExtractorProfileConfig
from idp_brain.ingestion.chunking import ChunkingPipeline
from idp_brain.ingestion.extractors import ArtifactExtractionContext, MarkdownExtractor
from idp_brain.ingestion.pipeline import run_ingestion
from idp_brain.ingestion.redaction_stage import RedactionStage
from idp_brain.models import Artifact, Chunk, Citation, IngestionRun
from idp_brain.repositories import (
    ArtifactExtractionRepository,
    ChunkRepository,
    CitationRepository,
)

from .conftest import assert_no_forbidden_ingestion_text


def test_public_ingestion_path_currently_stops_after_artifact_discovery(
    monkeypatch: pytest.MonkeyPatch,
    ingestion_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    run_result = _run_public_local_ingestion(
        monkeypatch,
        ingestion_session_factory,
        tmp_path,
    )

    with ingestion_session_factory() as session:
        artifacts = session.scalars(select(Artifact)).all()
        chunks = session.scalars(select(Chunk)).all()
        citations = session.scalars(select(Citation)).all()
        assert_no_forbidden_ingestion_text(session)

    assert run_result.status == "completed"
    assert {artifact.path for artifact in artifacts} == {"guide.md"}
    assert chunks == []
    assert citations == []


def test_manual_stage_composition_persists_safe_records_without_product_wiring(
    monkeypatch: pytest.MonkeyPatch,
    artifact_context_factory: Callable[..., ArtifactExtractionContext],
    extractor_profile: ExtractorProfileConfig,
    ingestion_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    run_result = _run_public_local_ingestion(
        monkeypatch,
        ingestion_session_factory,
        tmp_path,
    )

    with ingestion_session_factory() as session:
        artifact = session.scalars(
            select(Artifact).where(Artifact.path == "guide.md")
        ).one()
        artifact_id = artifact.id
        source_version_id = artifact.source_version_id

    extraction = MarkdownExtractor().extract(
        artifact_context_factory(
            "guide.md",
            "documentation",
            source_id="source:ingestion-e2e",
            source_version_id=source_version_id,
            artifact_id=artifact_id,
        ),
        Path("tests/fixtures/ingestion/local/guide.md").read_bytes(),
    )
    redacted = RedactionStage(
        load_security_config(Path("config/security.yaml"))
    ).redact(extraction)
    chunking = ChunkingPipeline(extractor_profile).chunk_result(redacted)

    with ingestion_session_factory() as session:
        run = session.get(IngestionRun, run_result.run_id)
        artifact = session.get(Artifact, artifact_id)
        assert run is not None
        assert artifact is not None
        extraction_row = ArtifactExtractionRepository(
            session
        ).create_from_sanitized_result(redacted, ingestion_run_id=run.id)
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
        artifacts = session.scalars(select(Artifact)).all()
        assert_no_forbidden_ingestion_text(session)

    assert run_result.status == "completed"
    assert chunks
    assert citations
    assert all(chunk.extraction_id == extraction_row.id for chunk in chunks)
    assert all(artifact.visibility_label == "invited_users" for artifact in artifacts)
    assert all(chunk.source_id == "source:ingestion-e2e" for chunk in chunks)
    assert all(chunk.source_version_id is not None for chunk in chunks)
    assert all(chunk.sanitized_content_hash for chunk in chunks)
    assert all(citation.sanitized_content_hash for citation in citations)


def _run_public_local_ingestion(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
):
    repository_root = Path.cwd()
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.local_directory.REPOSITORY_ROOT",
        repository_root,
    )
    monkeypatch.setattr(
        "idp_brain.ingestion.fetchers.local_directory.FIXTURE_ALLOWLIST_ROOT",
        repository_root / "tests" / "fixtures" / "ingestion",
    )
    return run_ingestion(
        config_path=_write_local_config(tmp_path),
        source_id="ingestion-e2e",
        dry_run=False,
        session_factory=session_factory,
    )[0]


def _write_local_config(tmp_path: Path) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(
        """---
config_version: 1
kind: sources
sources:
  - source_id: ingestion-e2e
    source_type: local_directory
    local_path: tests/fixtures/ingestion/local
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
    sensitivity_class: confidential
    license_policy: review_required
    refresh_cadence: manual
    enabled: true
""",
        encoding="utf-8",
    )
    return path
