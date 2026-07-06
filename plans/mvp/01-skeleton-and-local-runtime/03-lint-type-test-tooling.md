# 1.3: Lint Type Test Tooling

## Goal
Install and configure baseline validation tools so Python formatting checks, linting, type checking, and tests run consistently through `mise` locally and later in CI.

## Prerequisites
- Phase 1.1 and Phase 1.2 are complete.
- Read `ARCHITECTURE.md`, especially `Extraction And Validation Tools` and `GitHub Actions`.
- `uv` and `mise` are available locally.

## Files To Create Or Modify
- `pyproject.toml`
- `uv.lock`
- `mise.toml`
- `tests/`

## Implementation Instructions
1. Add development dependencies for `ruff`, `mypy`, and `pytest-cov`; keep the `pytest` dependency introduced in Phase 1.1.
2. Configure Ruff in `pyproject.toml` for Python 3.12 and the `src` plus `tests` paths.
3. Configure mypy in `pyproject.toml` to type check `src/idp_brain` with deterministic, project-appropriate strictness:
   - `python_version = "3.12"`
   - disallow untyped definitions
   - warn on unused ignores
   - warn on redundant casts
   - no implicit optional values
4. Configure pytest in `pyproject.toml` to discover tests under `tests` and to avoid depending on external services by default.
5. Update `mise run lint` to run these checks in order:
   - `uv run ruff format --check .`
   - `uv run ruff check .`
   - `uv run mypy src/idp_brain`
6. Update `mise run test` to run `uv run pytest`.
7. Update `mise run ci` to run `mise run lint` then `mise run test`.
8. Fix any scaffold code or tests so the new checks pass.
9. Do not add database, ingestion, retrieval, MCP, embedding, reranking, or external model dependencies in this step.

## Tests And Checks
- `uv sync`
- `mise run lint`
- `mise run test`
- `mise run ci`
- Passing condition: formatting check, linting, type checking, and tests all exit 0 without external services.

## Acceptance Criteria
- Validation commands are deterministic and exposed through `mise`.
- Type checking covers `src/idp_brain`.
- The initial test suite passes without PostgreSQL, Docker, network access, source catalogs, or model provider credentials.
- No raw source data can be loaded, persisted, embedded, logged, or returned by tooling added in this step.

## Suggested Commit Message
`chore: add lint type and test tooling`
