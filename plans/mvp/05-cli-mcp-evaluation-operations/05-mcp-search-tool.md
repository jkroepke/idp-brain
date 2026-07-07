# 5.5: MCP Search Tool

## Goal
Implement the read-only MCP `search` tool for hybrid evidence retrieval, returning sanitized evidence bundle summaries and citation IDs through the same retrieval service as the CLI.

## Prerequisites
- Step 5.4 has added the MCP stdio server.
- Step 5.2 has added the shared retrieval query path.
- Phase 4 exact, BM25, vector, relationship traversal, fusion, reranking, corpus eligibility filtering, and evidence packaging are complete.
- `ARCHITECTURE.md` remains the source of truth for the `search` tool input schema and output safety contract.

## Files To Create Or Modify
- `src/idp_brain/mcp/tools.py`
- `src/idp_brain/mcp/schemas.py`
- `src/idp_brain/mcp/safety.py`
- `src/idp_brain/retrieval/service.py`
- `tests/mcp/test_search_tool.py`
- `tests/mcp/test_search_tool_safety.py`

## Implementation Instructions
1. Register an MCP tool named `search`.
2. Define the input schema exactly with these fields from `ARCHITECTURE.md`:
   - `query: str`
   - `source_ids: list[str] | None = None`
   - `source_types: list[str] | None = None`
   - `version: str | None = None`
   - `time_or_release_range: str | None = None`
   - `caller_context_hint: str | None = None`
   - `include_conflicts: bool | None = None`
   - `max_results: int | None = None`
   - `token_budget: int | None = None`
3. Apply configured bounds to `query`, filter arrays, `caller_context_hint`, `max_results`, and `token_budget` before calling retrieval.
4. Treat `caller_context_hint` only as an untrusted ranking or query-disambiguation hint. It must not grant source eligibility, bypass corpus eligibility filters, alter sensitivity rules, or override trusted corpus scope.
5. Call the shared retrieval service with trusted corpus scope derived server-side.
6. Ensure every retrieval subquery applies source allowlist, license, sensitivity, redaction, version, and active-index filters before exact lookup, BM25, vector search, relationship traversal, reranking, and packaging.
7. Return sanitized evidence bundle summaries with citation IDs, selected chunk IDs, source metadata, freshness metadata, conflict markers, redaction status, and token budget estimate.
8. Do not return raw unsanitized chunks, raw fetched files, embedding vectors, SQL, vector-store internals, reranker payloads, pre-filter diagnostics, or direct database locators.
9. Ensure result snippets come only from sanitized chunk text that has passed corpus eligibility and redaction checks.
10. Log only sanitized metadata: tool name, bounded input sizes, result count, redaction status, corpus eligibility filter summary, latency, and correlation ID.

## Tests And Checks
- `uv run pytest tests/mcp/test_search_tool.py tests/mcp/test_search_tool_safety.py`
- `mise run ci`
- Tests must cover schema validation, default behavior, source filters, source type filters, version and range filters, `include_conflicts`, result limiting, token budget limiting, caller context hint non-trust, empty-result abstention, sanitized output, and safe logs.

## Acceptance Criteria
- MCP `search` accepts exactly the MVP schema and returns citation-backed sanitized evidence summaries.
- The tool is read-only and does not expose SQL, vector-store access, ingestion mutation, configuration mutation, or raw chunks.
- `caller_context_hint` cannot influence trusted corpus scope.
- Local and CI tests pass with fixture retrieval, mock embeddings, and mock reranking.

## Suggested Commit Message
`feat: add mcp search tool`
