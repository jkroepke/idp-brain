# 5.2: Retrieve Query Command

## Goal
Add `idp-brain retrieve query` as the primary local command for hybrid retrieval, returning source-backed evidence bundle summaries and citation IDs from the same retrieval service used by MCP.

## Prerequisites
- Phase 1 CLI scaffolding is complete.
- Phase 4 exact, BM25, vector, fusion, reranking, corpus eligibility filtering, and evidence bundle assembly are complete.
- Sanitized chunks, citations, index versions, and retrieval events are persisted.
- `config/retrieval.yaml`, `config/corpus.yaml`, and `config/security.yaml` exist.
- `ARCHITECTURE.md` remains the source of truth for the evidence bundle contract and retrieval safety model.

## Files To Create Or Modify
- `src/idp_brain/cli.py`
- `src/idp_brain/cli/retrieve.py`
- `src/idp_brain/retrieval/service.py`
- `src/idp_brain/retrieval/schemas.py`
- `src/idp_brain/retrieval/formatting.py`
- `src/idp_brain/retrieval/events.py`
- `tests/cli/test_retrieve_query_command.py`
- `tests/retrieval/test_retrieve_query_safety.py`
- `mise.toml`

## Implementation Instructions
1. Register a Typer sub-application at `idp-brain retrieve`.
2. Add `idp-brain retrieve query QUERY` with options:
   - `--profile TEXT`, defaulting to the configured default query profile.
   - `--source-id TEXT`, repeatable source filter.
   - `--source-type TEXT`, repeatable source-type filter.
   - `--version TEXT`, optional version, tag, branch, release, checksum, or explicit ref.
   - `--time-or-release-range TEXT`, optional range string passed through to retrieval scope parsing.
   - `--include-conflicts/--no-include-conflicts`, default from `config/retrieval.yaml`.
   - `--max-results INTEGER`, bounded by configuration.
   - `--token-budget INTEGER`, bounded by configuration.
   - `--json`, returning machine-readable evidence bundles.
3. Call the internal retrieval service rather than issuing SQL, pgvector, ParadeDB, or reranker calls directly from the CLI.
4. Build trusted corpus scope from local configuration and stored source metadata. Do not treat any caller-provided note, prompt, shell environment variable, or free-form context as trusted corpus eligibility.
5. Ensure the retrieval service applies source allowlists, corpus eligibility filters, sensitivity filters, license policy filters, redaction filters, version filters, and active-index filters before exact lookup, BM25, vector search, relationship traversal, reranking, event logging, and output formatting.
6. Return a concise Rich table by default with rank, citation ID, source ID, version, locator/path, line range, score or rank explanation summary, freshness marker, conflict marker, and sanitized excerpt.
7. JSON output must follow the evidence bundle contract: query, normalized query intent, selected chunk IDs, sanitized excerpts, citations, source authority ranking, freshness metadata, conflict markers, corpus eligibility filter result, redaction status, and token budget estimate.
8. Never print raw unsanitized chunks, raw fetched files, embedding vectors, direct SQL, vector-store internals, pre-filter decisions, or reranker provider payloads.
9. Add or update `mise run retrieve -- <query>` so it delegates to `idp-brain retrieve query <query>`.
10. Provide deterministic local and CI behavior by allowing fixture indexes to use mock embeddings and mock reranking when external providers are unavailable.

## Tests And Checks
- `uv run idp-brain retrieve --help`
- `uv run idp-brain retrieve query --help`
- `uv run idp-brain retrieve query "how do I configure sources?" --json`
- `uv run pytest tests/cli/test_retrieve_query_command.py tests/retrieval/test_retrieve_query_safety.py`
- `mise run retrieve -- "fixture query"`
- `mise run ci`
- Tests must cover query profile selection, filters, token budget limiting, conflict inclusion, empty-result abstention, sanitized output, JSON schema shape, retrieval event creation, and deterministic mock provider fallback.

## Acceptance Criteria
- `idp-brain retrieve query` returns citation-backed sanitized evidence summaries for configured fixture data.
- The command uses the shared retrieval service and does not expose SQL, vector-store access, raw chunks, or provider internals.
- Source allowlist, license, sensitivity, redaction, version, and active-index filters are applied before candidate generation and output.
- Local and CI tests pass without external embedding or reranking services.
- `mise run retrieve -- <query>` works as the documented local task.

## Suggested Commit Message
`feat: add retrieve query command`
