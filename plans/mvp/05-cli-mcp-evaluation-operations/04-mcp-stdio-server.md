# 5.4: MCP Stdio Server

## Goal
Add a local MCP stdio server that exposes read-only retrieval tools to agents while keeping ingestion, database administration, SQL, vector-store access, model serving, and workflow state outside MCP.

## Prerequisites
- Phase 1 package and CLI scaffolding are complete.
- Phase 4 retrieval service and evidence bundle assembly are complete.
- Steps 5.2 and 5.3 have established shared retrieval query and diagnostics paths.
- The MCP Python SDK is available through `pyproject.toml` and `uv.lock`.
- `ARCHITECTURE.md` remains the source of truth for MCP scope, read-only behavior, and tool contracts.

## Files To Create Or Modify
- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/cli.py`
- `src/idp_brain/mcp/__init__.py`
- `src/idp_brain/mcp/server.py`
- `src/idp_brain/mcp/tools.py`
- `src/idp_brain/mcp/schemas.py`
- `src/idp_brain/mcp/safety.py`
- `tests/mcp/test_stdio_server.py`
- `tests/mcp/test_mcp_read_only_contract.py`
- `mise.toml`

## Implementation Instructions
1. Add the MCP Python SDK dependency pinned through `uv.lock`.
2. Add `idp-brain mcp serve` with options:
   - `--transport stdio`, the only supported MVP transport.
   - `--config-dir PATH`, defaulting to `config/`.
   - `--log-level TEXT`, defaulting to a safe non-verbose level.
3. Do not add HTTP transport in this step. HTTP requires authentication and deployment policy that are not part of the MVP.
4. Create the MCP server with stdio transport and register only these read-only tools:
   - `search`
   - `fetch`
   - `explain_search`
   - `list_sources`
5. Route all tool calls through application services. MCP handlers must not execute SQL, call pgvector or ParadeDB directly, expose vector-store handles, mutate ingestion state, change configuration, write memory, activate index versions, or run external workflows.
6. Derive trusted corpus scope on the server side from local configuration and stored source metadata. Treat `caller_context_hint` as an untrusted hint only.
7. Use Pydantic schemas for tool inputs and outputs. Bound string lengths, result counts, and token budgets by configuration before calling retrieval services.
8. Ensure server logs contain tool name, sanitized request metadata, correlation ID, redaction status, result counts, and latency only. Logs must not contain raw unsanitized chunks, raw source files, full prompts, secrets, PII, vectors, SQL, or provider payloads.
9. Add `mise run mcp` if the project task list includes local MCP startup; otherwise document `uv run idp-brain mcp serve --transport stdio` in command help only.
10. Keep deterministic tests local by using an in-process MCP client, fixture retrieval services, mock embeddings, and mock reranking.

## Tests And Checks
- `uv run idp-brain mcp serve --help`
- `uv run pytest tests/mcp/test_stdio_server.py tests/mcp/test_mcp_read_only_contract.py`
- `mise run ci`
- Tests must verify tool registration, stdio transport startup, schema validation, bounded inputs, read-only service calls, safe logging, no HTTP transport exposure, and no ingestion/database/admin tools.

## Acceptance Criteria
- The MCP server starts over stdio and exposes exactly the MVP read-only retrieval tools.
- MCP handlers use shared application services and never expose SQL, vector-store access, ingestion mutation, configuration mutation, or index promotion.
- `caller_context_hint` is never used as trusted corpus scope.
- Logs and tool responses contain sanitized evidence and metadata only.
- CI can test the server deterministically without external network, embedding, or reranking services.

## Suggested Commit Message
`feat: add read-only mcp stdio server`
