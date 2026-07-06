# 3.1: Sources List Command

## Goal
Add a read-only `idp-brain sources list` command that loads `config/sources.yaml`, applies configuration validation, and displays source catalog metadata without fetching, ingesting, persisting, embedding, or returning source content.

## Prerequisites
- Phase 1 is complete, including the Typer CLI, `mise` tasks, lint, type, and test tooling.
- Phase 2.1 and Phase 2.2 are complete, including typed configuration loading and example config files.
- `ARCHITECTURE.md` remains the source of truth for source types, source metadata, access labels, sensitivity labels, and license policy labels.

## Files To Create Or Modify
- `src/idp_brain/cli.py`
- `src/idp_brain/config/__init__.py`
- `src/idp_brain/config/sources.py`
- `src/idp_brain/ingestion/__init__.py`
- `src/idp_brain/ingestion/source_catalog.py`
- `config/sources.yaml`
- `tests/fixtures/config/sources_valid.yaml`
- `tests/fixtures/config/sources_invalid.yaml`
- `tests/test_sources_list_command.py`

## Implementation Instructions
1. Add a `sources` Typer command group and a `list` subcommand exposed as `idp-brain sources list`.
2. Load source definitions through the Phase 2 configuration loader instead of parsing YAML directly in the CLI.
3. Support `--config config/sources.yaml`, `--format table`, and `--format json`; default to table output for humans and keep JSON stable for tests.
4. Display only catalog metadata: stable source ID, source type, tracked refs or version strategy, extractor profile, source priority, visibility label, access policy label or allowed-principal summary, sensitivity class, license policy, refresh cadence, and enabled state.
5. Validate source types against the architecture-supported set: `git_repository`, `git_repository_digest`, `release_artifact`, `documentation_site`, `documentation_file`, `openapi_spec`, `schema_bundle`, and `local_directory`.
6. Validate that each source carries access, license, and sensitivity fields before it can be listed as enabled.
7. Do not fetch remote URLs, inspect local directories, read upstream source files, create ingestion runs, write database records, generate embeddings, or emit chunks from this command.
8. Redact configured secrets in error messages by routing config-load errors through the project diagnostic formatter from Phase 2 if one exists; otherwise include only field paths and validation messages, never full config values for secret-like fields.
9. Add a `mise` task only if Phase 1 did not already expose a generic CLI task; prefer `uv run idp-brain sources list --config config/sources.yaml` in documentation and tests.

## Tests And Checks
- `uv run idp-brain sources list --config tests/fixtures/config/sources_valid.yaml --format json`
- `uv run idp-brain sources list --config tests/fixtures/config/sources_valid.yaml --format table`
- `uv run pytest tests/test_sources_list_command.py`
- `mise run lint`
- `mise run test`
- Passing condition: the command lists valid source metadata deterministically, rejects invalid source definitions with non-secret diagnostics, and performs no network, filesystem source inspection, database writes, or embedding work.

## Acceptance Criteria
- `idp-brain sources list` is read-only and side-effect free.
- The command works locally and in CI with fixture configuration only.
- Every listed source includes visibility, access, sensitivity, and license policy metadata.
- No raw upstream source content, raw chunks, embeddings, retrieval records, or ingestion run records are produced.
- Invalid source definitions fail before any fetch or ingestion work could begin.

## Suggested Commit Message
`feat: add sources list command`
