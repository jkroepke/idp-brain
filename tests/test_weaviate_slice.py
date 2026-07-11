from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from idp_brain.ingestion.chunking import ChunkingPipeline
from idp_brain.ingestion.extractors import ArtifactExtractionContext, MarkdownExtractor
from idp_brain.ingestion.redaction_stage import RedactionStage
from idp_brain.weaviate_slice import evidence_uuid, upsert_evidence_chunk


class _Data:
    def __init__(self) -> None:
        self.properties: dict[str, object] | None = None

    def replace(self, *, uuid: object, properties: dict[str, object]) -> None:
        self.properties = properties

    def insert(self, *, uuid: object, properties: dict[str, object]) -> None:
        self.properties = properties

    def exists(self, uuid: object) -> bool:
        return self.properties is not None


class _Collection:
    def __init__(self, data: _Data) -> None:
        self.data = data


class _Collections:
    def __init__(self, data: _Data) -> None:
        self._data = data

    def use(self, name: str) -> _Collection:
        return _Collection(self._data)


class _Client:
    def __init__(self) -> None:
        self.data = _Data()
        self.collections = _Collections(self.data)


def test_weaviate_boundary_accepts_only_redacted_content() -> None:
    result = _fixture_chunks()
    index = next(
        index
        for index, chunk in enumerate(result.chunks)
        if "[REDACTED" in chunk.sanitized_text
    )
    chunk, citation = result.chunks[index], result.citations[index]
    client = _Client()

    object_id = upsert_evidence_chunk(
        client, chunk, citation, extractor_version="markdown-v1"
    )

    assert object_id == evidence_uuid(chunk.chunk_key)
    assert client.data.properties is not None
    content = client.data.properties["content"]
    assert "ada@example.test" not in content
    assert "sk-test-ingestion-secret" not in content
    assert "hunter2-ingestion" not in content
    assert "[REDACTED" in content
    assert client.data.properties["citationId"] == citation.citation_key
    assert client.data.properties["contentHash"] == chunk.sanitized_content_hash

    unsafe = replace(chunk, redaction_status="pending")
    with pytest.raises(ValueError, match="only redacted chunks"):
        upsert_evidence_chunk(client, unsafe, citation, extractor_version="markdown-v1")


def test_evidence_uuid_is_deterministic() -> None:
    assert evidence_uuid("chunk:example") == evidence_uuid("chunk:example")
    assert evidence_uuid("chunk:example") != evidence_uuid("chunk:other")


def _fixture_chunks():
    context = ArtifactExtractionContext(
        artifact_id="artifact:guide",
        source_id="source:ingestion-e2e",
        source_version_id="sha256:fixture-v1",
        path="guide.md",
        logical_locator="https://example.test/docs/guide.md",
        source_type="local_directory",
        artifact_role="documentation",
        language="markdown",
        extractor_profile="docs_markdown_html",
        visibility_label="invited_users",
        sensitivity_class="confidential",
        license_policy_label="review_required",
        corpus_eligibility_label="review_required",
    )
    extracted = MarkdownExtractor().extract(
        context, Path("tests/fixtures/ingestion/local/guide.md").read_bytes()
    )
    return ChunkingPipeline().chunk_result(RedactionStage().redact(extracted))
