# 5.6: MCP Fetch Tool

## Goal
Implement the read-only MCP `fetch` tool for retrieving sanitized evidence content for a specific citation, chunk, artifact locator, or versioned source reference by ID.

## Prerequisites
- Step 5.4 has added the MCP stdio server.
- Step 5.5 has added MCP `search` and citation-producing evidence bundles.
- Citations, chunks, artifacts, source versions, access labels, sensitivity labels, and redaction status are persisted.
- `ARCHITECTURE.md` remains the source of truth for the `fetch` input schema and sanitized evidence contract.

## Files To Create Or Modify
- `src/idp_brain/mcp/tools.py`
- `src/idp_brain/mcp/schemas.py`
- `src/idp_brain/mcp/safety.py`
- `src/idp_brain/retrieval/fetch.py`
- `src/idp_brain/retrieval/schemas.py`
- `tests/mcp/test_fetch_tool.py`
- `tests/mcp/test_fetch_tool_safety.py`

## Implementation Instructions
1. Register an MCP tool named `fetch`.
2. Define the input schema exactly with these fields from `ARCHITECTURE.md`:
   - `citation_id: str | None = None`
   - `chunk_id: str | None = None`
   - `artifact_id: str | None = None`
   - `source_version_id: str | None = None`
   - `line_range: object | None = None`
   - `token_budget: int | None = None`
3. Validate that at least one of `citation_id`, `chunk_id`, or `artifact_id` is present. Return a validation error when none are supplied.
4. For `line_range`, accept a structured object with `start: int` and `end: int`, both positive, inclusive, and bounded by configuration.
5. Use `source_version_id` only as an additional scope constraint. It must not bypass citation, ACL, sensitivity, license, redaction, or source allowlist checks.
6. Call a shared retrieval fetch service that derives trusted access context server-side and returns only sanitized evidence content.
7. Return sanitized evidence content, citation metadata, source ID, source version ID, path or logical locator, line range when available, commit/tag/version/checksum, source type, sanitized content hash, redaction status, visibility label, and sensitivity class.
8. Do not return raw unsanitized chunks, full raw files, direct filesystem paths to local ingestion cache, SQL, vector-store access, embeddings, hidden ACL details, or provider payloads.
9. Apply token budget and line range after ACL and redaction checks. Truncation must preserve citation metadata and clearly mark the response as truncated.
10. Log only sanitized metadata, bounded identifiers, redaction status, result size, and latency.

## Tests And Checks
- `uv run pytest tests/mcp/test_fetch_tool.py tests/mcp/test_fetch_tool_safety.py`
- `mise run ci`
- Tests must cover citation fetch, chunk fetch, artifact fetch, source-version scoping, line range validation, token budget truncation, missing ID validation, not-found behavior, denied access behavior, sanitized output, and safe logs.

## Acceptance Criteria
- MCP `fetch` accepts exactly the MVP schema and returns sanitized evidence for a specific allowed citation, chunk, or artifact locator.
- Access, source allowlist, sensitivity, license, and redaction checks run before content is returned.
- The tool is read-only and exposes no raw chunks, local cache files, SQL, vector-store access, ingestion mutation, or provider internals.
- Local and CI tests are deterministic and require no external services.

## Suggested Commit Message
`feat: add mcp fetch tool`
