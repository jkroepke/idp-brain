# 4.13: Retrieval Test Suite

## Goal
Add the retrieval regression test suite that validates sanitized exact, BM25, vector, bounded relationship, fused, reranked, and evidence-bundle behavior locally and in CI.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Steps 4.1 through 4.12 are complete.
- Local runtime can start PostgreSQL with `vector`, `pg_search`, and `pg_trgm`.
- CI can run deterministic embedding and reranking tests with mock providers and no external API calls.
- Phase 3 fixtures can create sanitized chunks, citations, claims, conflicts, and redaction markers.
- Relationship fixtures can create normalized PostgreSQL lineage, dependency, conflict, and impact edges between allowed and disallowed entities or chunks.

## Files To Create Or Modify
- `tests/retrieval/conftest.py`
- `tests/retrieval/fixtures.py`
- `tests/retrieval/test_exact_lookup.py`
- `tests/retrieval/test_bm25_retrieval.py`
- `tests/retrieval/test_vector_retrieval.py`
- `tests/retrieval/test_query_profiles.py`
- `tests/retrieval/test_access_filtering.py`
- `tests/retrieval/test_reciprocal_rank_fusion.py`
- `tests/retrieval/test_reranking_integration.py`
- `tests/retrieval/test_evidence_bundle_contract.py`
- `tests/retrieval/test_hybrid_retrieval_regressions.py`
- `tests/db/test_retrieval_migrations.py`
- `.github/workflows/ci.yaml`

## Implementation Instructions
1. Build a deterministic sanitized fixture corpus with documentation chunks, code chunks, schema/API chunks, release-note chunks, conflict-claim chunks, and redaction-marker chunks.
2. Build deterministic normalized relationship fixtures for lineage, dependency, conflict, and impact edges, including cycles, high-fanout nodes, unauthorized endpoints, source-disallowed endpoints, sensitivity-disallowed endpoints, license-disallowed endpoints, and uncited endpoints.
3. Store only sanitized fixture content in the database. If a test needs to prove secret redaction safety, keep the raw secret literal inside the test assertion setup only long enough to verify it is absent from persisted chunks, embeddings, logs, evidence bundles, and diagnostics.
4. Use the deterministic mock embedding provider and deterministic mock reranker by default in tests.
5. Add integration tests for ParadeDB BM25 and pgvector only under markers such as `requires_pg_search` and `requires_pgvector`. The default unit suite must remain deterministic without external APIs.
6. Ensure CI starts the local Postgres service through repository tasks and verifies `vector`, `pg_search`, and `pg_trgm` before running integration tests.
7. Cover the required retrieval categories:
   - exact identifier lookup
   - source-code lookup
   - schema/API lookup
   - documentation lookup
   - release/version lookup
   - change-to-version lookup
   - version diff retrieval
   - bounded lineage traversal
   - bounded dependency traversal
   - bounded impact traversal
   - source-vs-doc conflict retrieval
   - conflict-edge traversal with both allowed sides preserved
   - stale source detection
   - retrieval with source filters
   - retrieval with token budget limits
   - BM25-only, vector-only, exact-only, and fused hybrid comparisons
   - secret redaction
   - PII redaction
   - license policy filtering
8. Add tests proving filters run before exact, BM25, vector, relationship, memory, diagnostics, CLI-facing, and MCP-facing retrieval helpers. Memory, CLI, and MCP helpers may be placeholders at this phase; bounded relationship traversal is a Phase 4 retrieval service contract and must have active tests.
9. Add relationship traversal tests proving ACL, source, sensitivity, license, redaction, citation, version, and active-index filters are applied before traversal, and proving configured depth, fanout, candidate, type, direction, and cycle bounds are enforced.
10. Add regression tests that BM25 scores and vector distances are never directly compared or added during fusion.
11. Add evidence bundle snapshot tests for sanitized excerpts, citations, conflict markers, relationship path metadata, filter results, and diagnostics.
12. Add CI commands to run:
    - `mise run lint`
    - `mise run test`
    - `mise run db:migrate`
    - `uv run pytest tests/retrieval`
13. Keep evaluation thresholds and MCP tool implementation out of this step unless `config/evaluation.yaml` already defines them. Retrieval test failures are functional regressions; metric gates and CLI/MCP implementation are Phase 5 work.

## Tests And Checks
- `mise run lint`
- `mise run test`
- `mise run db:migrate`
- `uv run pytest tests/retrieval`
- `uv run pytest tests/db/test_retrieval_migrations.py`
- `uv run pytest tests/retrieval -m "requires_pg_search or requires_pgvector"` when the local extension-enabled database is running.
- Verify that CI uses mock embedding and mock reranking unless external providers are explicitly enabled for a separate, non-default job.
- Verify that no test fixture, log capture, evidence snapshot, embedding job, or retrieval event persists raw unsanitized chunks.
- Verify that relationship tests cover lineage, dependency, conflict, and impact behavior using normalized PostgreSQL relationships and bounded traversal settings.

## Acceptance Criteria
- Phase 4 retrieval behavior is covered by deterministic unit tests and extension-backed integration tests.
- Exact, BM25, vector, bounded relationship, query profile, filtering, fusion, reranking, and evidence-bundle behavior can be validated locally and in CI.
- Safety constraints for redaction, ACL/source/sensitivity/license filters, bounded relationship traversal, sanitized evidence, and score-domain separation are regression-tested.
- External embedding or reranking services are not required for CI.
- The suite provides the baseline retrieval confidence needed before downstream CLI/MCP surfaces and Phase 5 evaluation and operations work; Phase 4 tests service contracts, not MCP tool implementation.

## Suggested Commit Message
`test: add retrieval regression suite`
