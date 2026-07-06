# 1.6: Alembic Base And Extension Migration

## Goal
Add Alembic migration infrastructure and the first migration that enables PostgreSQL extensions required by `ARCHITECTURE.md`: `vector`, `pg_search`, and `pg_trgm`.

## Prerequisites
- Phase 1.1 through Phase 1.5 are complete.
- Read `ARCHITECTURE.md`, especially `Database`, `Hybrid Retrieval Store`, `Data Model`, and `Local Runtime`.
- `mise run up` starts local PostgreSQL.

## Files To Create Or Modify
- `pyproject.toml`
- `uv.lock`
- `alembic.ini`
- `migrations/env.py`
- `migrations/script.py.mako`
- `migrations/versions/0001_enable_extensions.py`
- `src/idp_brain/db.py`
- `mise.toml`
- `tests/integration/test_migrations_smoke.py`

## Implementation Instructions
1. Add runtime dependencies for SQLAlchemy 2, Alembic, and Psycopg 3, using the SQLAlchemy driver form `postgresql+psycopg`.
2. Create a SQLAlchemy engine helper in `src/idp_brain/db.py` that reads `Settings.database_url`.
3. Keep the database helper small: engine/session construction only, no ORM product tables in this step.
4. Initialize Alembic under `migrations/`.
5. Configure `migrations/env.py` to load project settings and connect with SQLAlchemy.
6. Create migration `0001_enable_extensions.py` that executes exactly these statements:
   - `CREATE EXTENSION IF NOT EXISTS vector`
   - `CREATE EXTENSION IF NOT EXISTS pg_search`
   - `CREATE EXTENSION IF NOT EXISTS pg_trgm`
7. Add `mise run db:migrate` to apply `alembic upgrade head`.
8. Add `mise run test:integration` for database-backed tests, initially running `uv run pytest -m integration tests/integration`.
9. Keep default `mise run test` database-free by marking integration tests with `@pytest.mark.integration` and excluding that marker from the default test task.
10. Add or update `mise run db:reset` only if it is implemented safely and clearly as a destructive local-only disposable database reset; otherwise keep it deferred with a clear non-zero message.
11. Keep downgrade behavior explicit. Dropping extensions is not required for local development, but if downgrade is a no-op, document that it avoids destructive removal of shared local extensions.
12. Do not create application tables, BM25 indexes, HNSW indexes, ingestion records, chunks, embeddings, citations, or retrieval events yet.

## Tests And Checks
- `mise run up`
- `mise run db:migrate`
- `docker compose exec postgres psql -U idp_brain -d idp_brain -c "SELECT extname FROM pg_extension WHERE extname IN ('vector','pg_search','pg_trgm') ORDER BY extname;"`
- `mise run test:integration`
- `mise run lint`
- Passing condition: Alembic upgrades a fresh disposable database, all three extension names are present, integration tests pass only when explicitly requested, and the default test task remains database-free.

## Acceptance Criteria
- Alembic can recreate extension state from a fresh disposable database.
- Required extensions are migration-managed, not manually configured through ad hoc local commands.
- The migration does not create product tables or indexes beyond extension metadata.
- Database-backed tests are isolated from default unit tests and run through an explicit `mise` task.
- No raw source data is loaded, persisted, embedded, logged, returned, or sent to model providers.

## Suggested Commit Message
`feat: add alembic extension migration`
