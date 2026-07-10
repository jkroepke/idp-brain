# 1.8: GitHub Actions CI

## Goal
Add the initial GitHub Actions workflow that runs linting, type checking, tests, migrations, and the PostgreSQL extension smoke test against an ephemeral database using the same `mise` commands as local development.

## Prerequisites
- Phase 1.1 through Phase 1.7 are complete.
- Read `ARCHITECTURE.md`, especially `GitHub Actions`, `Mise Tasks`, `Local Runtime`, and `Security Model`.
- All checks pass locally through `mise`.

## Files To Create Or Modify
- `.github/workflows/ci.yaml`
- `mise.toml`
- `README.md` only if CI status or command documentation is needed

## Implementation Instructions
1. Create `.github/workflows/ci.yaml`.
2. Trigger on pull requests and pushes to the default branch.
3. Use one Linux job with repository checkout, Python 3.14 through `mise`, dependency installation through `mise run install`, and the same Docker Compose PostgreSQL runtime used locally.
4. Configure CI environment variables explicitly:
   - `IDP_BRAIN_EXTERNAL_MODEL_CALLS_ENABLED=false`
   - `IDP_BRAIN_EMBEDDING_PROVIDER=mock`
   - `IDP_BRAIN_DATABASE_URL` pointing at the ephemeral compose database
5. Update `mise run ci` to run the complete Phase 1 validation path in order: install if needed, lint, run default database-free tests through `mise run test`, start PostgreSQL, apply migrations, run database-backed tests through `mise run test:integration`, and stop PostgreSQL in cleanup.
6. In the workflow, run `mise run ci` as the main validation command rather than duplicating raw internal commands.
7. Ensure cleanup stops the compose stack even if checks fail.
8. Keep the CI database ephemeral. Do not assume access to a durable server database.
9. Do not add scheduled ingestion, evaluation workflows, dependency review, artifact promotion, remote model serving, or index snapshot upload in this step.
10. Do not add secrets. The workflow must not call external model providers, persist ingestion output, or promote index versions.

## Tests And Checks
- `mise run ci`
- Passing condition: local CI task passes, workflow syntax is valid, and the workflow uses only ephemeral local services plus dependency installation.

## Acceptance Criteria
- CI validates Python formatting, linting, type checking, tests, migration application, and database extension compatibility.
- CI uses the same documented `mise` commands as local development.
- CI disables external model calls explicitly.
- CI does not persist ingestion output, upload raw source caches, or promote index versions.
- The workflow contains no secrets and no scheduled ingestion or evaluation jobs.

## Suggested Commit Message
`ci: add initial validation workflow`
