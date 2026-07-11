# 6.10: Remove PostgreSQL, ParadeDB, And pgvector

## Goal

Delete the temporary source backend and all compatibility code so the final project has one persistent platform and no stale database maintenance surface.

## Prerequisites

- Step 6.9 has activated and validated Weaviate.
- The observation window is complete.
- Backup, restore, rebuild, and rollback tests pass.

## Files To Remove Or Modify

- `docker-compose.yaml`
- `pyproject.toml`
- `uv.lock`
- `mise.toml`
- `.env.example`
- settings and database modules
- Alembic configuration and migration files
- SQLAlchemy models and repositories
- psycopg helpers
- ParadeDB and pgvector retrieval modules
- PostgreSQL CI services and extension smoke tests
- PostgreSQL backup and observability configuration
- documentation and examples

## Implementation Instructions

1. Remove the PostgreSQL and ParadeDB services from the default and migration Compose profiles.
2. Remove dependencies that are no longer used:
   - SQLAlchemy.
   - Alembic.
   - psycopg and psycopg2.
   - pgvector Python integration.
   - ParadeDB-specific helpers.
   - PostgreSQL-only test libraries.
3. Delete database migration files, extension bootstrap, BM25 SQL, HNSW SQL, and schema smoke tests.
4. Delete the old exact, BM25, vector, reciprocal-rank-fusion, and SQL relationship retrieval implementations when they are not used by another non-database concern.
5. Remove embedding job tables and workers replaced by Weaviate vectorization. Keep only an explicit external/BYOV workflow if it is a supported final profile.
6. Remove temporary dual-backend flags, shadow adapters, export commands, and PostgreSQL migration tasks.
7. Rename generic `db:*` tasks and settings to `weaviate:*` or `store:*` where appropriate.
8. Replace PostgreSQL backup, restore, health, metrics, and trace assumptions with Weaviate equivalents.
9. Update CI to start only Weaviate and deterministic vectorization fixtures.
10. Update all docs, examples, environment files, diagrams, and comments.
11. Add repository checks that fail on unexpected runtime references to:
    - `DATABASE_URL`.
    - `pg_search`.
    - `pgvector`.
    - `postgres` service names.
    - SQLAlchemy or Alembic imports.
    - psycopg imports.
12. Do not retain a generic backend interface whose only purpose is preserving deleted code.
13. Keep historical Phase 1 through Phase 5 plan files as migration history, but mark Phase 4 as the old baseline in the plan overview.

## Tests And Checks

- `uv sync --locked`
- `docker compose config`
- Start the complete default runtime and verify no PostgreSQL container exists.
- Run static searches for removed dependencies and configuration names.
- Run all ingestion, retrieval, CLI, MCP, evaluation, backup, restore, and observability tests.
- Verify a clean environment needs no PostgreSQL client or extension packages.
- `mise run ci`

## Acceptance Criteria

- Weaviate is the only required persistent service.
- No old database runtime dependency remains.
- No temporary migration or dual-backend code remains.
- CI and local development work without PostgreSQL tooling.
- Documentation contains no stale PostgreSQL target architecture.

## Suggested Commit Message

`refactor: remove postgres retrieval stack`
