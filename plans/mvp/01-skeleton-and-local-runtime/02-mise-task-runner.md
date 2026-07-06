# 1.2: Mise Task Runner

## Goal
Add `mise` as the documented workflow entry point so contributors can install dependencies, run checks, and later control the local runtime through stable task names from `ARCHITECTURE.md`.

## Prerequisites
- Phase 1.1 is complete.
- Read `ARCHITECTURE.md`, especially `Exact Tool Suite`, `Mise Tasks`, and `Local Runtime`.
- `mise` and `uv` are available locally.

## Files To Create Or Modify
- `mise.toml`
- `README.md` if a short local development section does not already exist

## Implementation Instructions
1. Create `mise.toml` with Python 3.12 pinned for the project.
2. Add exactly these required task names from `ARCHITECTURE.md`: `install`, `up`, `down`, `db:migrate`, `db:reset`, `ingest`, `retrieve`, `eval`, `lint`, `test`, and `ci`.
3. Wire implemented tasks in this step as follows:
   - `install`: `uv sync`
   - `test`: `uv run pytest`
   - `lint`: a deterministic available check such as `uv run python -m compileall src tests` until Ruff and mypy are added in Phase 1.3
   - `ci`: run `lint` then `test` through `mise`
4. Make deferred tasks fail fast with a non-zero exit and a precise message naming the owning future step:
   - `up` and `down`: implemented in Phase 1.4
   - `db:migrate` and `db:reset`: implemented in Phase 1.6 or later
   - `ingest`: implemented in Phase 3
   - `retrieve`: implemented in Phase 5
   - `eval`: implemented in Phase 5
5. Ensure `retrieve` accepts extra arguments syntactically for the future `mise run retrieve -- <query>` interface, even if it currently fails as deferred.
6. Keep `retrieve` deferred in this step so no retrieval path can accidentally bypass the future ACL, source allowlist, sensitivity, and license filters required by `ARCHITECTURE.md`.
7. Add `README.md` usage notes that say normal workflows should use `mise run <task>` and list the implemented Phase 1.2 commands.
8. Do not add database, ingestion, retrieval, MCP, model-provider, or product behavior yet.

## Tests And Checks
- `mise run install`
- `mise run lint`
- `mise run test`
- `mise run ci`
- `mise tasks`
- One deferred-task check, for example `mise run db:migrate`, must exit non-zero and print the expected future-step message.
- Passing condition: implemented tasks run successfully, deferred tasks fail clearly, and all required task names are visible.

## Acceptance Criteria
- `mise.toml` is the documented command surface for local workflows.
- The task names match the required list in `ARCHITECTURE.md`.
- `mise run ci` is deterministic and uses only local checks available after Phase 1.2.
- Deferred tasks cannot be mistaken for successful no-ops.
- No product code outside task wiring and README usage notes is changed.

## Suggested Commit Message
`chore: add mise task runner`
