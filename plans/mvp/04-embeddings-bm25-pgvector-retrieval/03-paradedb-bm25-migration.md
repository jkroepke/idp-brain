# 4.3: ParadeDB BM25 Migration

## Goal
Add the migration-managed ParadeDB BM25 index over sanitized chunks and selected metadata fields used by retrieval profiles.

## Prerequisites
- Phase 1 extension smoke tests can create `pg_search`.
- Phase 3 has created the `chunks` table with sanitized text and retrieval metadata.
- Raw unsanitized chunk columns do not exist in Postgres.
- The local Docker image used by `mise run up` includes ParadeDB `pg_search`.

## Files To Create Or Modify
- `alembic/versions/<revision>_chunks_bm25_index.py`
- `tests/db/test_paradedb_bm25_migration.py`
- `tests/retrieval/test_bm25_extension_smoke.py`
- `src/idp_brain/db/migration_checks.py`

## Implementation Instructions
1. In the Alembic upgrade, verify or rely on the Phase 1 migration that runs `CREATE EXTENSION IF NOT EXISTS pg_search`.
2. Create a BM25 index named `chunks_bm25_idx` on `chunks` using the sanitized and filterable fields from `ARCHITECTURE.md`:
   ```sql
   CREATE INDEX chunks_bm25_idx
   ON chunks
   USING bm25 (
       id,
       sanitized_text,
       heading_path,
       symbol_path,
       signature_text,
       artifact_path,
       source_type,
       language,
       version_label,
       visibility_label,
       sensitivity_class
   )
   WITH (key_field = 'id');
   ```
3. Include only columns that exist after Phase 3, but keep the migration review explicit if a named architecture field is missing. Do not replace `sanitized_text` with raw text.
4. If `license_policy_status`, `source_id`, or `artifact_role` exists and profile queries need ranked metadata search or filter pushdown, include those fields after confirming ParadeDB supports the field type.
5. Add a downgrade that drops `chunks_bm25_idx` if it exists.
6. Add a migration check that fails when `pg_search` is absent in local runtime or CI integration tests.
7. Add a fixture insert with sanitized chunks only, including one row that contains a redaction marker such as `[REDACTED_SECRET]`.
8. Add a smoke query that uses the BM25 index and returns `pdb.score(id)` for a sanitized query. Keep this as an index smoke test, not the final retrieval implementation.
9. When `pg_search` is unavailable in a unit-test-only environment, run SQL generation checks and mark the integration test with a clear `requires_pg_search` marker instead of silently substituting PostgreSQL FTS as the product path.

## Tests And Checks
- `mise run db:migrate`
- `uv run pytest tests/db/test_paradedb_bm25_migration.py`
- `uv run pytest tests/retrieval/test_bm25_extension_smoke.py -m requires_pg_search`
- Verify that `chunks_bm25_idx` exists after migration and is absent after downgrade.
- Verify that BM25 fixture queries return only sanitized chunk IDs and scores.
- Verify that no migration SQL references raw chunk text or extractor output tables.

## Acceptance Criteria
- ParadeDB BM25 is migration-managed and reproducible from an empty database.
- The BM25 index is built over sanitized chunks and approved metadata only.
- Local and CI extension compatibility failures are detected early.
- PostgreSQL native FTS is not promoted to the primary lexical retrieval layer.
- BM25 scores remain BM25 diagnostics and are not compared directly with vector distances.

## Suggested Commit Message
`feat: add paradedb bm25 index migration`
