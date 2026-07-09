from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from idp_brain.config import load_security_config
from idp_brain.config.models import ExtractorProfileConfig
from idp_brain.ingestion.chunking import ChunkingPipeline
from idp_brain.ingestion.extractors import (
    ArtifactExtractionContext,
    JsonExtractor,
    MarkdownExtractor,
    SourceCodeExtractor,
)
from idp_brain.ingestion.redaction_stage import RedactionStage, UnredactedCandidateError
from idp_brain.models import (
    Artifact,
    Base,
    Chunk,
    Citation,
    IngestionRun,
    Source,
    SourceVersion,
)
from idp_brain.repositories import (
    ArtifactExtractionRepository,
    ChunkRepository,
    CitationRepository,
)

EXTRACTOR_FIXTURES = Path("tests/fixtures/extractors")
REDACTION_FIXTURE = Path("tests/fixtures/redaction/unsafe.md")
RAW_SECRETS = ("sk-test-secret", "hunter2", "alice@example.test")


def test_markdown_chunks_have_stable_ids_and_citations() -> None:
    extraction = MarkdownExtractor().extract(
        _artifact("doc.md", "documentation"),
        (EXTRACTOR_FIXTURES / "doc.md").read_bytes(),
    )
    result = RedactionStage().redact(extraction)
    pipeline = ChunkingPipeline(_profile())

    first = pipeline.chunk_result(result, extraction_id="extraction:chunking")
    second = pipeline.chunk_result(result, extraction_id="extraction:chunking")

    assert first.chunks
    assert [chunk.chunk_key for chunk in first.chunks] == [
        chunk.chunk_key for chunk in second.chunks
    ]
    assert [citation.citation_key for citation in first.citations] == [
        citation.citation_key for citation in second.citations
    ]
    assert all(chunk.sanitized_text for chunk in first.chunks)
    assert all(chunk.redaction_status == "redacted" for chunk in first.chunks)
    assert all(
        chunk.visibility_label == "invited_users"
        and chunk.corpus_eligibility_label == "review_required"
        and chunk.license_policy_label in {"allowed", "review_required"}
        for chunk in first.chunks
    )
    assert any(chunk.heading_path for chunk in first.chunks)
    assert any(chunk.chunk_kind == "code_block" for chunk in first.chunks)
    assert all(
        citation.source_type == "local_directory" for citation in first.citations
    )


def test_structured_and_source_code_chunks_preserve_context() -> None:
    json_result = RedactionStage().redact(
        JsonExtractor().extract(
            _artifact("data.json", "example"),
            (EXTRACTOR_FIXTURES / "data.json").read_bytes(),
        )
    )
    code_result = RedactionStage().redact(
        SourceCodeExtractor().extract(
            _artifact("sample.py", "source_code", language="python"),
            (EXTRACTOR_FIXTURES / "sample.py").read_bytes(),
        )
    )
    pipeline = ChunkingPipeline(_profile(chunk_size_chars=500))

    json_chunks = pipeline.chunk_result(json_result).chunks
    code_chunks = pipeline.chunk_result(code_result).chunks

    assert any(
        chunk.metadata.get("json_pointer") and chunk.chunk_kind == "structured_scalar"
        for chunk in json_chunks
    )
    widget_render = next(
        chunk for chunk in code_chunks if chunk.symbol_path == "Widget.render"
    )
    assert widget_render.signature_text == "def render(self, value)"
    assert widget_render.language == "python"
    assert widget_render.metadata["parent_symbol_path"] == ["Widget"]
    assert "pathlib" in widget_render.metadata["imports"]


def test_structured_chunk_provenance_persists() -> None:
    result = RedactionStage().redact(
        JsonExtractor().extract(
            _artifact("data.json", "example"),
            (EXTRACTOR_FIXTURES / "data.json").read_bytes(),
        )
    )
    chunking = ChunkingPipeline(_profile(chunk_size_chars=500)).chunk_result(result)
    structured_chunk = next(
        chunk for chunk in chunking.chunks if chunk.metadata.get("json_pointer")
    )
    structured_citation = chunking.citations[chunking.chunks.index(structured_chunk)]

    engine = create_engine("sqlite:///:memory:", future=True)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            _add_minimal_graph(session, artifact_id="artifact:data.json")
            chunk_row = ChunkRepository(session).upsert_chunk(structured_chunk)
            CitationRepository(session).upsert_citation(
                structured_citation,
                chunk_id=chunk_row.id,
            )
            session.commit()

            persisted_chunk = session.get(Chunk, chunk_row.id)
            persisted_citation = session.get(Citation, structured_citation.citation_key)
            assert persisted_chunk is not None
            assert persisted_citation is not None
            assert persisted_chunk.corpus_eligibility_label == "review_required"
            assert persisted_citation.corpus_eligibility_label == "review_required"
            assert persisted_chunk.structure_path == list(
                structured_chunk.structure_path
            )
            assert persisted_chunk.metadata_["json_pointer"]
            assert persisted_chunk.metadata_["chunker_profile"] == "structured-data-v1"
            assert persisted_chunk.metadata_["schema_version"] == (
                "sanitized-chunks-v1"
            )
    finally:
        engine.dispose()


def test_chunking_rejects_unredacted_candidates() -> None:
    result = _redacted_markdown()
    unsafe = replace(
        result,
        candidates=(replace(result.candidates[0], redaction_status="unknown"),),
    )

    with pytest.raises(UnredactedCandidateError):
        ChunkingPipeline(_profile()).chunk_result(unsafe)


def test_persisted_chunks_and_citations_contain_no_raw_secret_values() -> None:
    result = _redacted_markdown()
    chunking = ChunkingPipeline(_profile()).chunk_result(result)

    engine = create_engine("sqlite:///:memory:", future=True)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            _add_minimal_graph(session)
            extraction_row = ArtifactExtractionRepository(
                session
            ).create_from_sanitized_result(
                result,
                ingestion_run_id="ingestion:chunking",
            )
            chunk_repository = ChunkRepository(session)
            citation_repository = CitationRepository(session)
            for chunk, citation in zip(
                chunking.chunks, chunking.citations, strict=True
            ):
                chunk = replace(chunk, extraction_id=extraction_row.id)
                chunk_row = chunk_repository.upsert_chunk(chunk)
                chunk_repository.upsert_chunk_version(chunk_row=chunk_row)
                citation_repository.upsert_citation(citation, chunk_id=chunk_row.id)
            session.commit()

            chunks = session.scalars(select(Chunk)).all()
            citations = session.scalars(select(Citation)).all()
            assert chunks
            assert citations
            assert {chunk.id for chunk in chunks} == {
                chunk.chunk_key for chunk in chunking.chunks
            }
            assert all(
                chunk.corpus_eligibility_label == "review_required" for chunk in chunks
            )
            assert all(
                citation.corpus_eligibility_label == "review_required"
                for citation in citations
            )
            assert all(citation.commit_sha == "abc123" for citation in citations)
            assert all(citation.tag == "v1.0.0" for citation in citations)
            assert all(citation.version == "1.0.0" for citation in citations)
            assert all(
                citation.checksum == "sha256:source-version" for citation in citations
            )
            persisted = "\n".join(
                [
                    *(chunk.sanitized_text for chunk in chunks),
                    *(chunk.sanitized_content_hash for chunk in chunks),
                    *(citation.sanitized_content_hash for citation in citations),
                    *(citation.source_url for citation in citations),
                ]
            )
            for raw_secret in RAW_SECRETS:
                assert raw_secret not in persisted
    finally:
        engine.dispose()


def _redacted_markdown():
    security = load_security_config(Path("config/security.yaml"))
    extraction = MarkdownExtractor().extract(
        _artifact(
            "unsafe.md",
            "documentation",
            sensitivity_class="confidential",
            logical_locator="fixture:password=hunter2",
        ),
        REDACTION_FIXTURE.read_bytes(),
    )
    return RedactionStage(security).redact(extraction)


def _artifact(
    path: str,
    role: str,
    *,
    language: str | None = None,
    sensitivity_class: str = "internal",
    logical_locator: str | None = None,
) -> ArtifactExtractionContext:
    return ArtifactExtractionContext(
        artifact_id=f"artifact:{path}",
        source_id="source:chunking",
        source_version_id="source-version:chunking",
        path=path,
        logical_locator=logical_locator or f"fixture:{path}",
        source_type="local_directory",
        artifact_role=role,
        language=language,
        extractor_profile="fixture_profile",
        visibility_label="invited_users",
        sensitivity_class=sensitivity_class,
        license_policy_label="review_required",
        corpus_eligibility_label="review_required",
    )


def _profile(
    *,
    chunk_size_chars: int = 1200,
    chunk_overlap_chars: int = 120,
) -> ExtractorProfileConfig:
    return ExtractorProfileConfig.model_validate(
        {
            "profile_id": "fixture_profile",
            "family": "docs",
            "enabled": True,
            "file_patterns": ["**/*"],
            "include_generated": False,
            "include_vendored": False,
            "tools": [
                {
                    "tool_id": "builtin-fixture",
                    "enabled": True,
                    "command": [],
                    "options": {
                        "chunk_size_chars": chunk_size_chars,
                        "chunk_overlap_chars": chunk_overlap_chars,
                    },
                }
            ],
            "validator_commands": [],
            "fallback_profile": None,
        }
    )


def _add_minimal_graph(
    session: Session,
    *,
    artifact_id: str = "artifact:unsafe.md",
) -> None:
    session.add(
        Source(
            id="source:chunking",
            config_key="chunking-source",
            name="Chunking Source",
            source_type="local_directory",
            repository_url="https://example.test/repo.git",
            visibility_label="invited_users",
            sensitivity_class="confidential",
            license_policy_status="review_required",
            redaction_status="redacted",
        )
    )
    session.add(
        SourceVersion(
            id="source-version:chunking",
            source_id="source:chunking",
            version_label="snapshot",
            repository_url="https://example.test/repo.git",
            commit_sha="abc123",
            tag="v1.0.0",
            version="1.0.0",
            checksum="sha256:source-version",
            is_current=True,
            visibility_label="invited_users",
            sensitivity_class="confidential",
            license_policy_status="review_required",
            redaction_status="redacted",
        )
    )
    session.add(
        IngestionRun(
            id="ingestion:chunking",
            source_id="source:chunking",
            source_version_id="source-version:chunking",
            requested_ref="snapshot",
            status="completed",
            stats={},
        )
    )
    session.add(
        Artifact(
            id=artifact_id,
            artifact_key=artifact_id.removeprefix("artifact:"),
            artifact_type="document",
            artifact_role="documentation",
            path=artifact_id.removeprefix("artifact:"),
            source_id="source:chunking",
            source_version_id="source-version:chunking",
            source_type="local_directory",
            repository_url="https://example.test/repo.git",
            visibility_label="invited_users",
            sensitivity_class="confidential",
            license_policy_status="review_required",
            redaction_status="redacted",
            corpus_eligibility_label="review_required",
        )
    )
    session.flush()
