from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from idp_brain.config import load_security_config
from idp_brain.config.models import ExtractorProfileConfig
from idp_brain.ingestion.chunking import ChunkingPipeline
from idp_brain.ingestion.extractors import ArtifactExtractionContext, MarkdownExtractor
from idp_brain.ingestion.redaction_stage import RedactionStage
from idp_brain.models import Chunk, Citation
from idp_brain.repositories import (
    ArtifactExtractionRepository,
    ChunkRepository,
    CitationRepository,
)

from .conftest import assert_no_forbidden_ingestion_text


def test_chunking_persists_metadata_and_sanitized_citations(
    artifact_context_factory: Callable[..., ArtifactExtractionContext],
    extractor_profile: ExtractorProfileConfig,
    add_ingestion_graph,
    ingestion_session_factory: sessionmaker[Session],
) -> None:
    extraction = MarkdownExtractor().extract(
        artifact_context_factory("guide.md", "documentation"),
        Path("tests/fixtures/ingestion/local/guide.md").read_bytes(),
    )
    redacted = RedactionStage(
        load_security_config(Path("config/security.yaml"))
    ).redact(extraction)
    chunking = ChunkingPipeline(extractor_profile).chunk_result(redacted)

    with ingestion_session_factory() as session:
        add_ingestion_graph(session)
        extraction_row = ArtifactExtractionRepository(
            session
        ).create_from_sanitized_result(redacted, ingestion_run_id="ingestion:run")
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
    assert all(chunk.sanitized_content_hash.startswith("sha256:") for chunk in chunks)
    assert all(chunk.redaction_status == "redacted" for chunk in chunks)
    assert all(chunk.visibility_label == "invited_users" for chunk in chunks)
    assert all(chunk.corpus_eligibility_label == "review_required" for chunk in chunks)
    assert all(citation.commit_sha == "abc123" for citation in citations)
    assert all(citation.version_label == "snapshot" for citation in citations)
