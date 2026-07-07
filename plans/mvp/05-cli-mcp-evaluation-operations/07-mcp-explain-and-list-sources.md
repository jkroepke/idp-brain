# 5.7: MCP Explain Search And List Sources Tools

## Goal
Implement MCP `explain_search` and `list_sources` so agents can inspect retrieval diagnostics and indexed source metadata without gaining write access or direct database/vector-store access.

## Prerequisites
- Step 5.4 has added the MCP stdio server.
- Steps 5.5 and 5.6 have added MCP `search` and `fetch`.
- Step 5.3 has added sanitized retrieval explain diagnostics.
- Source, source version, index version, freshness, visibility, and ingestion status metadata are persisted.
- `ARCHITECTURE.md` remains the source of truth for MCP tool names, diagnostics, listable source metadata, and safety constraints.

## Files To Create Or Modify
- `src/idp_brain/mcp/tools.py`
- `src/idp_brain/mcp/schemas.py`
- `src/idp_brain/mcp/safety.py`
- `src/idp_brain/retrieval/explain.py`
- `src/idp_brain/sources/listing.py`
- `tests/mcp/test_explain_search_tool.py`
- `tests/mcp/test_list_sources_tool.py`
- `tests/mcp/test_mcp_diagnostic_safety.py`

## Implementation Instructions
1. Register an MCP tool named `explain_search`.
2. Use the same input schema as MCP `search` for `explain_search`:
   - `query: str`
   - `source_ids: list[str] | None = None`
   - `source_types: list[str] | None = None`
   - `version: str | None = None`
   - `time_or_release_range: str | None = None`
   - `caller_context_hint: str | None = None`
   - `include_conflicts: bool | None = None`
   - `max_results: int | None = None`
   - `token_budget: int | None = None`
3. Treat `caller_context_hint` as untrusted and never as corpus eligibility context.
4. Return sanitized diagnostics for query profile, active index version, filters applied, exact lookup hits, BM25 ranks, vector ranks, relationship traversal hits, fusion rank, reranker rank, selected citations, competing citations, source authority, freshness, conflict markers, token budget effects, and abstention reasons.
5. Do not return raw chunks, raw source files, SQL, query plans with sensitive literals, vectors, provider payloads, pre-filter eligibility details, or direct vector-store/database access details.
6. Register an MCP tool named `list_sources`.
7. Define the `list_sources` input schema as:
   - `source_ids: list[str] | None = None`
   - `source_types: list[str] | None = None`
   - `visibility_labels: list[str] | None = None`
   - `version: str | None = None`
   - `include_inactive: bool | None = None`
   - `limit: int | None = None`
   - `cursor: str | None = None`
8. `list_sources` must derive trusted corpus scope server-side and list only sources and versions eligible for that scope.
9. `list_sources` output must include source ID, source type, visible version labels, freshness or last verified timestamp, active index version, ingestion status summary, visibility label, sensitivity class, license policy status, and pagination cursor when needed.
10. `list_sources` must not expose configured secrets, credentials, private repository tokens, raw source URLs when policy marks them sensitive, local cache paths, SQL, or vector-store internals.
11. Keep both tools read-only and deterministic in CI with fixture metadata.

## Tests And Checks
- `uv run pytest tests/mcp/test_explain_search_tool.py tests/mcp/test_list_sources_tool.py tests/mcp/test_mcp_diagnostic_safety.py`
- `mise run ci`
- Tests must cover `explain_search` schema parity with `search`, diagnostic redaction, caller context hint non-trust, abstention explanations, source listing filters, pagination, corpus-filtered source visibility, and absence of raw chunks, SQL, vectors, credentials, and local cache paths.

## Acceptance Criteria
- MCP `explain_search` returns sanitized retrieval diagnostics with selected and competing citation IDs.
- MCP `list_sources` returns corpus-filtered source, version, freshness, visibility, sensitivity, license, and ingestion metadata.
- Both tools are read-only and expose no SQL, vector-store access, ingestion mutation, raw chunks, secrets, or provider internals.
- Local and CI tests are deterministic and require no external services.

## Suggested Commit Message
`feat: add mcp explain and source listing tools`
