from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest
import weaviate
from weaviate.auth import Auth
from weaviate.exceptions import InsufficientPermissionsError

from idp_brain.ingestion.chunking import ChunkingPipeline
from idp_brain.ingestion.extractors import ArtifactExtractionContext, MarkdownExtractor
from idp_brain.ingestion.redaction_stage import RedactionStage
from idp_brain.weaviate_slice import (
    COLLECTION_NAME,
    bootstrap_collection,
    configure_reader_role,
    hybrid_search,
    upsert_evidence_chunk,
)

pytestmark = pytest.mark.integration

WRITER_KEY = os.getenv("IDP_BRAIN_WEAVIATE_WRITER_KEY", "local-mvp52-writer-key")
READER_KEY = os.getenv("IDP_BRAIN_WEAVIATE_READER_KEY", "local-mvp52-reader-key")


def test_fixture_round_trips_through_hybrid_client_and_read_only_mcp() -> None:
    http_port = int(os.getenv("IDP_BRAIN_WEAVIATE_HTTP_PORT", "58080"))
    grpc_port = int(os.getenv("IDP_BRAIN_WEAVIATE_GRPC_PORT", "50051"))
    chunks = _fixture_chunks()
    index = next(
        index
        for index, chunk in enumerate(chunks.chunks)
        if "[REDACTED" in chunk.sanitized_text
    )
    chunk, citation = chunks.chunks[index], chunks.citations[index]

    with weaviate.connect_to_local(
        port=http_port,
        grpc_port=grpc_port,
        auth_credentials=Auth.api_key(WRITER_KEY),
    ) as client:
        if client.collections.exists(COLLECTION_NAME):
            client.collections.delete(COLLECTION_NAME)
        bootstrap_collection(client)
        upsert_evidence_chunk(client, chunk, citation, extractor_version="markdown-v1")
        configure_reader_role(client, reader_user="idp-brain-reader")

    with weaviate.connect_to_local(
        port=http_port,
        grpc_port=grpc_port,
        auth_credentials=Auth.api_key(READER_KEY),
    ) as client:
        matches = hybrid_search(client, "safe ingestion guide")
        with pytest.raises(InsufficientPermissionsError):
            upsert_evidence_chunk(
                client, chunk, citation, extractor_version="markdown-v1"
            )

    assert matches
    assert matches[0].properties["chunkId"] == chunk.chunk_key
    assert matches[0].properties["citationId"] == citation.citation_key
    assert "sk-test-ingestion-secret" not in matches[0].properties["content"]

    session_id = _initialize_mcp(http_port)
    tools, session_id = _mcp_request(
        http_port, "tools/list", request_id=2, session_id=session_id
    )
    tool_names = {tool["name"] for tool in tools["result"]["tools"]}
    assert "weaviate-query-hybrid" in tool_names
    assert "weaviate-objects-upsert" not in tool_names

    result, _ = _mcp_request(
        http_port,
        "tools/call",
        request_id=3,
        session_id=session_id,
        params={
            "name": "weaviate-query-hybrid",
            "arguments": {
                "collection_name": COLLECTION_NAME,
                "query": "safe ingestion guide",
                "limit": 5,
                "target_vectors": ["content"],
                "return_properties": ["chunkId", "content", "citationId"],
            },
        },
    )
    serialized = json.dumps(result)
    assert chunk.chunk_key in serialized
    assert citation.citation_key in serialized
    assert "sk-test-ingestion-secret" not in serialized


def _mcp_request(
    port: int,
    method: str,
    *,
    request_id: int,
    session_id: str | None = None,
    params: dict[str, object] | None = None,
) -> tuple[dict[str, object], str | None]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {READER_KEY}",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    response = httpx.post(
        f"http://127.0.0.1:{port}/v1/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            **({"params": params} if params else {}),
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload, response.headers.get("mcp-session-id") or session_id


def _initialize_mcp(port: int) -> str:
    response, session_id = _mcp_request(
        port,
        "initialize",
        request_id=1,
        params={
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "idp-brain-test", "version": "1"},
        },
    )
    assert response["result"]["protocolVersion"]
    assert session_id is not None
    initialized = httpx.post(
        f"http://127.0.0.1:{port}/v1/mcp",
        headers={
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {READER_KEY}",
            "Mcp-Session-Id": session_id,
        },
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        timeout=30,
    )
    initialized.raise_for_status()
    return session_id


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
