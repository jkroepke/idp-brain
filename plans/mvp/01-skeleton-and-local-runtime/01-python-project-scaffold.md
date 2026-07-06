# 1.1: Python Project Scaffold

## Goal
Create the minimal Python 3.14 package skeleton for `idp-brain` with an installable Typer CLI and a smoke test, aligned with the `ARCHITECTURE.md` runtime language, CLI, and local-first boundaries.

## Prerequisites
- Read `ARCHITECTURE.md`, especially `Runtime Language`, `CLI And Optional API`, `Security Model`, and `Repository Boundary`.
- `uv` is available locally.
- No prior MVP implementation steps are required.

## Files To Create Or Modify
- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/__init__.py`
- `src/idp_brain/cli.py`
- `tests/test_cli_smoke.py`
- `.gitignore`

## Implementation Instructions
1. Create a `src`-layout Python package named `idp-brain` that imports as `idp_brain`.
2. Set `requires-python = ">=3.14,<3.15"` in `pyproject.toml`.
3. Add runtime dependencies only for `typer` and `rich`.
4. Add an initial development dependency for `pytest` because this step owns `tests/test_cli_smoke.py`; later validation tooling is added in Phase 1.3.
5. Add a console script named `idp-brain` that points to `idp_brain.cli:app`.
6. Implement `src/idp_brain/cli.py` as a Typer app with exactly these supported behaviors in this step:
   - `idp-brain --help`
   - `idp-brain version`
7. Keep the CLI read-only and side-effect free. It must not read source catalogs, start services, open network connections, call external models, create caches, connect to PostgreSQL, or inspect local ingestion data.
8. Put the package version in one place, such as `src/idp_brain/__init__.py`, and have the `version` command print that value.
9. Add `.gitignore` entries for `.venv/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `__pycache__/`, `.coverage`, `dist/`, build artifacts, and local ingestion/cache directories such as `.idp-brain-cache/` or `var/`.
10. Generate and commit `uv.lock`.

## Tests And Checks
- `uv sync`
- `uv run idp-brain --help`
- `uv run idp-brain version`
- `uv run pytest tests/test_cli_smoke.py`
- Passing condition: the package installs, CLI help renders, the version command exits 0, and the smoke test passes without external services.

## Acceptance Criteria
- The repository has a valid Python 3.14 package using `src/idp_brain`.
- `idp-brain` is available as a console command through `uv run`.
- No product behavior beyond CLI help and version output exists yet.
- No raw source ingestion, persistence, embedding, logging, model call, database access, or retrieval behavior is introduced.

## Suggested Commit Message
`chore: scaffold python project`
