# 5.3: Retrieve Explain Command

## Goal
Add `idp-brain retrieve explain` for retrieval diagnostics that explain why evidence was selected or rejected without exposing raw chunks, direct database access, pre-filter eligibility details, vectors, or unsafe provider payloads.

## Prerequisites
- Step 5.2 has added `idp-brain retrieve query`.
- Phase 4 retrieval diagnostics exist for exact lookup, BM25, vector retrieval, relationship traversal, fusion, reranking, and evidence packaging.
- Retrieval events are stored using sanitized query text, sanitized metadata, selected chunk IDs, citation IDs, and score components.
- `ARCHITECTURE.md` remains the source of truth for debug output and the evidence bundle contract.

## Files To Create Or Modify
- `src/idp_brain/cli/retrieve.py`
- `src/idp_brain/retrieval/explain.py`
- `src/idp_brain/retrieval/schemas.py`
- `src/idp_brain/retrieval/formatting.py`
- `src/idp_brain/retrieval/events.py`
- `tests/cli/test_retrieve_explain_command.py`
- `tests/retrieval/test_retrieve_explain_safety.py`

## Implementation Instructions
1. Add `idp-brain retrieve explain QUERY` with options:
   - `--profile TEXT`, defaulting to the configured default query profile.
   - `--source-id TEXT`, repeatable source filter.
   - `--source-type TEXT`, repeatable source-type filter.
   - `--version TEXT`, optional version or release scope.
   - `--time-or-release-range TEXT`, optional range string.
   - `--include-conflicts/--no-include-conflicts`, default from configuration.
   - `--max-results INTEGER`, bounded by configuration.
   - `--token-budget INTEGER`, bounded by configuration.
   - `--show-competing INTEGER`, defaulting to a small configured count.
   - `--json`, returning machine-readable diagnostics.
2. Reuse the same retrieval request path as `retrieve query`, enabling diagnostics through a service-level flag rather than adding a second retrieval implementation.
3. Include sanitized diagnostics for query profile, active index version, corpus eligibility filter summary, source filters, sensitivity filters, version filters, exact match candidates, BM25 rank positions, vector rank positions, relationship traversal hits, fusion rank, reranker rank, source authority, freshness, citation completeness, conflict markers, and competing candidates.
4. Treat BM25 scores and vector distances as different domains. Diagnostics may show per-path scores, ranks, and fusion inputs, but must not imply direct numeric comparability unless calibrated by the retrieval service.
5. Explain abstention when no acceptable evidence is found, including which safe filters or thresholds caused exclusion.
6. Do not return raw unsanitized chunks, raw fetched files, SQL text, query plans containing sensitive literals, embedding vectors, reranker payloads, pre-filter eligibility details, or full sensitive chunk text.
7. Persist a retrieval event with sanitized diagnostic metadata and redaction status.
8. Keep deterministic CI behavior by using fixture indexes, mock embeddings, and mock reranking.

## Tests And Checks
- `uv run idp-brain retrieve explain --help`
- `uv run idp-brain retrieve explain "fixture symbol lookup" --json`
- `uv run pytest tests/cli/test_retrieve_explain_command.py tests/retrieval/test_retrieve_explain_safety.py`
- `mise run ci`
- Tests must verify output includes selected and competing citation IDs, rank components, filters applied, active index version, abstention reasons, and redaction status while excluding raw chunks, vectors, SQL, and pre-filter diagnostics.

## Acceptance Criteria
- `idp-brain retrieve explain` explains selected and competing evidence using sanitized diagnostics.
- The command shares the same retrieval service path as `retrieve query`.
- The output helps tune retrieval without bypassing corpus eligibility, redaction, citation, or evidence-bundle rules.
- Local and CI tests are deterministic and do not require external services.

## Suggested Commit Message
`feat: add retrieve explain command`
