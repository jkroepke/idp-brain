# 1.7: Extension Smoke Test

## Goal
Add an automated local and CI-ready smoke test proving PostgreSQL can use `vector`, `pg_search`, and `pg_trgm`, plus one ParadeDB BM25 index, one pgvector HNSW index, and matching fixture queries.

## Prerequisites
- Phase 1.1 through Phase 1.6 are complete.
- Read `ARCHITECTURE.md`, especially `Database`, `Hybrid Retrieval Store`, `Initial migration pattern`, `Initial query shape`, and `Local Runtime`.
- Local PostgreSQL is running and migrated.

## Files To Create Or Modify
- `tests/integration/test_postgres_extensions.py`
- `mise.toml`
- Optional: `src/idp_brain/db_smoke.py` if shared smoke-test helpers are useful

## Implementation Instructions
1. Write an integration test that connects to the configured database through `Settings.database_url` and the database helper from Phase 1.6.
2. Run the test in an isolated temporary schema named with a unique test suffix, and drop that schema during cleanup.
3. Ensure the required extensions exist before creating test objects. Use the Phase 1.6 migration path in normal setup; direct `CREATE EXTENSION IF NOT EXISTS` inside the test is allowed only as an idempotent assertion helper.
4. Create a fixture table with these columns:
   - `id text PRIMARY KEY`
   - `sanitized_text text NOT NULL`
   - `source_allowlisted boolean NOT NULL DEFAULT true`
   - `access_policy_id text NOT NULL DEFAULT 'public'`
   - `visibility_label text NOT NULL DEFAULT 'public'`
   - `sensitivity_class text NOT NULL DEFAULT 'public'`
   - `license_policy_status text NOT NULL DEFAULT 'allowed'`
   - `embedding vector(3) NOT NULL`
5. Insert only sanitized fixture rows such as short public documentation phrases. Do not include secrets, PII, upstream raw chunks, private source names, or real customer/project data.
6. Keep the fixture metadata fields aligned with the later retrieval rule that source allowlist, ACL/access policy, visibility, sensitivity, and license filters must run before exact, BM25, vector, relationship, memory, diagnostics, CLI, or MCP retrieval paths.
7. Create one ParadeDB BM25 index over the fixture key and sanitized text fields using `USING bm25` and a stable `key_field`.
8. Create one pgvector HNSW index using cosine ops over the `embedding` column.
9. Run one BM25 query with `|||` that returns the expected fixture row.
10. Run one vector query ordered by `<=>` that returns the expected fixture row.
11. Include these filter predicates in both fixture queries: `source_allowlisted = true`, `access_policy_id = 'public'`, `visibility_label = 'public'`, `sensitivity_class = 'public'`, and `license_policy_status = 'allowed'`.
12. Assert the extension names are present so failures identify whether the problem is missing `vector`, `pg_search`, `pg_trgm`, BM25, or HNSW support.
13. Update the explicit `mise run test:integration` task from Phase 1.6 to include this smoke test, and ensure `mise run ci` can run it after `mise run db:migrate`.
14. Do not add application tables, retrieval services, embedding providers, external model calls, or source ingestion.

## Tests And Checks
- `mise run up`
- `mise run db:migrate`
- `mise run test:integration`
- `mise run ci`
- Passing condition: the test creates both index types and both fixture queries return expected rows repeatedly against a disposable database.

## Acceptance Criteria
- Extension compatibility is proven by behavior, not only by extension presence.
- The test uses sanitized fixture content and no external services.
- The fixture includes source allowlist, ACL/access-policy, visibility, sensitivity, and license metadata fields for later filter-first retrieval work.
- BM25 and vector fixture queries include the same allowlist, access-policy, visibility, sensitivity, and license predicates required by later retrieval paths.
- The smoke test can run repeatedly against a disposable database locally and in CI.
- Failures clearly identify missing `vector`, `pg_search`, `pg_trgm`, BM25, or HNSW support.
- The test does not persist raw unsanitized chunks, embeddings from real source data, retrieval logs, or model-provider output.

## Suggested Commit Message
`test: add postgres extension smoke test`
