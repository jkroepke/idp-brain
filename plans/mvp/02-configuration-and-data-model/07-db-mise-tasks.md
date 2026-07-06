# 2.7: DB Mise Tasks

## Goal
Expose database schema workflows through documented `mise` tasks so contributors and CI can migrate, inspect, reset, and validate the local database without remembering raw Alembic commands.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 2.6 is complete.
- Alembic migrations recreate the full Phase 2 schema from a fresh local database.
- Local database state is disposable unless a later phase explicitly defines export, retention, restore checks, and index promotion.

## Files To Create Or Modify
- `mise.toml`
- `src/idp_brain/db.py`
- `src/idp_brain/cli.py` if CLI wrappers already exist and are the established pattern
- `tests/test_mise_db_tasks.py`

## Implementation Instructions
1. Ensure existing `mise run db:migrate` still applies all Alembic upgrades to head.
2. Add or verify `mise run db:current` to print the current Alembic revision.
3. Add or verify `mise run db:history` to show migration history.
4. Add `mise run db:check` to run a deterministic schema check against a local database, including required extensions and Phase 2 table presence.
5. Add `mise run db:reset` for disposable local development only. It must clearly target the local Docker Compose database and must not run against arbitrary production-like URLs. Use an explicit confirmation environment variable such as `IDP_BRAIN_CONFIRM_RESET=1` if the implementation can drop data.
6. Add `mise run db:revision -- <message>` only if the project wants a documented wrapper for creating future Alembic revisions. It must not autogenerate unrelated product changes.
7. Add `mise run db:validate-models` if needed to compare SQLAlchemy metadata against migrations without requiring any external service.
8. Ensure `mise run ci` runs the migration and schema checks against an ephemeral database, then tears it down or leaves only disposable local Docker state.
9. Do not add ingestion, retrieval, embedding, reranking, model serving, scheduled jobs, production HA, or remote database promotion behavior in this step.

## Tests And Checks
- `mise tasks`
- `mise run up`
- `mise run db:migrate`
- `mise run db:current`
- `mise run db:history`
- `mise run db:check`
- `IDP_BRAIN_CONFIRM_RESET=1 mise run db:reset`
- `mise run test`
- `mise run ci`
- Passing condition: all documented database tasks work locally and in CI with an ephemeral Postgres service and no external APIs.

## Acceptance Criteria
- Database workflows are discoverable through `mise`.
- Migrations can be applied, inspected, reset, and checked from documented commands.
- CI uses the same database tasks as local development.
- Reset behavior is guarded and limited to disposable local databases.
- No raw unsanitized chunks, embeddings, retrieval output, or external model calls are introduced.

## Suggested Commit Message
`chore: add database mise tasks`
