# 6.11: Migration Test Suite And Completion Gate

## Goal

Create the final automated gate proving that the Weaviate architecture is complete, reproducible, safe, and independent from the removed PostgreSQL stack.

## Prerequisites

- Steps 6.1 through 6.10 are complete.
- The repository contains only the final Weaviate runtime path.

## Files To Create Or Modify

- `tests/integration/test_weaviate_bootstrap.py`
- `tests/integration/test_weaviate_ingestion.py`
- `tests/integration/test_weaviate_retrieval.py`
- `tests/integration/test_weaviate_backup_restore.py`
- `tests/integration/test_full_rebuild.py`
- migration completion checks
- `.github/workflows/ci.yaml`
- `mise.toml`

## Required Gate

1. Start an empty pinned Weaviate instance.
2. Bootstrap all required collection generations.
3. Ingest deterministic sanitized fixtures from configured sources.
4. Re-run ingestion and prove deterministic IDs and no duplicates.
5. Validate source, version, chunk, citation, claim, relationship, memory, and evaluation object counts where those collections are enabled.
6. Run exact, BM25-only, vector-only, hybrid, structured, and citation fetch tests.
7. Verify source, visibility, sensitivity, license, redaction, version, active-state, generation, and memory-expiry filters.
8. Run the held-out retrieval evaluation suite and enforce configured thresholds.
9. Create a backup, destroy the instance, restore into an empty instance, and repeat retrieval checks.
10. Destroy the instance again, rebuild entirely from configured sources, and compare manifests and content-hash aggregates.
11. Verify no external provider key is required by CI.
12. Verify no runtime import or configuration references SQLAlchemy, Alembic, psycopg, pgvector, ParadeDB, or PostgreSQL.
13. Verify CLI and MCP start without `DATABASE_URL`.
14. Verify telemetry does not expose source content, vectors, credentials, or provider payloads.
15. Run the normal and free-threaded Python jobs when Phase 7 is complete.

## Tests And Checks

- `mise run weaviate:bootstrap`
- `mise run ingest`
- `mise run retrieve -- "fixture query"`
- `mise run eval`
- `mise run weaviate:backup`
- `mise run weaviate:restore-smoke-test`
- full rebuild test
- removed-dependency scan
- `mise run ci`

## Acceptance Criteria

- A clean checkout builds the complete store from sources.
- Re-ingestion is idempotent.
- Retrieval quality and safety gates pass.
- Backup restore and full rebuild both recover a working system.
- CLI, MCP, CI, and tests have no PostgreSQL dependency.
- Phase 6 can be declared complete and the old backend cannot be selected.

## Suggested Commit Message

`test: complete weaviate migration gate`
