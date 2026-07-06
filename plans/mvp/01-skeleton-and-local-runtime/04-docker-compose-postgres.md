# 1.4: Docker Compose Postgres

## Goal
Add a disposable local PostgreSQL 18 runtime for pgvector, ParadeDB `pg_search`, and `pg_trgm`, without assuming the stock `pgvector/pgvector:pg18` image contains ParadeDB.

## Prerequisites
- Phase 1.1 through Phase 1.3 are complete.
- Read `ARCHITECTURE.md`, especially `Database`, `Hybrid Retrieval Store`, and `Local Runtime`.
- Docker and Docker Compose are available locally.

## Files To Create Or Modify
- `docker-compose.yaml`
- `docker/postgres/Dockerfile` if a repository-owned image is used
- `docker/postgres/init/` only if initialization scripts are required by the selected image path
- `mise.toml`
- `.env.example` if compose variables are introduced before Phase 1.5

## Implementation Instructions
1. Add a `postgres` service in `docker-compose.yaml`.
2. Use PostgreSQL 18 with pgvector, ParadeDB `pg_search`, and `pg_trgm` available through one explicit approach:
   - an approved PostgreSQL-compatible image reference pinned to a tag or digest and documented in the compose file, or
   - a repository-owned `docker/postgres/Dockerfile` that installs PostgreSQL 18, pgvector, ParadeDB `pg_search`, and PostgreSQL contrib modules for `pg_trgm`.
3. Do not use `pgvector/pgvector:pg18` by itself unless the step also proves and documents that `pg_search` is present.
4. Configure safe disposable development defaults:
   - database: `idp_brain`
   - user: `idp_brain`
   - password: `idp_brain`
   - host port: `127.0.0.1:${IDP_BRAIN_POSTGRES_PORT:-55432}:5432`
5. Add a healthcheck that verifies PostgreSQL accepts connections with `pg_isready`; extension creation and index behavior are owned by Phases 1.6 and 1.7.
6. Update `mise run up` to start the compose stack with `docker compose up -d --build postgres`.
7. Update `mise run down` to stop the compose stack without deleting unrelated user data; use a separate `db:reset` task later for destructive reset behavior.
8. Keep volumes local and disposable. Any named volume must be clearly development-only and must not be described as production durability.
9. Do not add application schema, migrations, ingestion, retrieval, MCP, or model-provider behavior.

## Tests And Checks
- `mise run up`
- `docker compose ps`
- `docker compose exec postgres pg_isready -U idp_brain -d idp_brain`
- `mise run down`
- Passing condition: the `postgres` service builds or pulls, starts, reports healthy or ready, and stops cleanly.

## Acceptance Criteria
- Local PostgreSQL starts through `mise run up`.
- The selected image path is explicit and intended to support `vector`, `pg_search`, and `pg_trgm`.
- The local database is disposable and not treated as durable production state.
- Extension creation remains migration-managed in Phase 1.6, with behavioral verification in Phase 1.7.
- No raw source data, schema tables, ingestion, embedding, or retrieval behavior is introduced.

## Suggested Commit Message
`chore: add local postgres runtime`
