# 5.1: Ingest CLI Commands

## Goal
Add the documented ingestion operator commands `idp-brain ingest run` and `idp-brain ingest status` so local developers and CI can start an ingestion run or inspect recent ingestion state through the same Typer CLI surface.

## Prerequisites
- Phase 1 CLI scaffolding is complete.
- Phase 2 source catalog, access policy, and ingestion run persistence are complete.
- Phase 3 sanitized extraction, redaction, chunking, and ingestion diagnostics are complete.
- Phase 4 indexing can write inactive `index_versions` records without promoting them automatically.
- `ARCHITECTURE.md` remains the source of truth for CLI behavior, ingestion stages, safety policy, and validation-only scheduled ingestion.

## Files To Create Or Modify
- `src/idp_brain/cli.py`
- `src/idp_brain/cli/ingest.py`
- `src/idp_brain/ingestion/orchestrator.py`
- `src/idp_brain/ingestion/status.py`
- `src/idp_brain/settings.py`
- `tests/cli/test_ingest_commands.py`
- `tests/fixtures/config/sources.yaml`
- `tests/fixtures/config/extractors.yaml`
- `mise.toml`

## Implementation Instructions
1. Register a Typer sub-application at `idp-brain ingest`.
2. Add `idp-brain ingest run` with options:
   - `--source-id TEXT`, repeatable filter for configured sources.
   - `--version TEXT`, optional requested tag, branch, release, checksum, or explicit ref.
   - `--profile TEXT`, optional extractor or ingestion profile name.
   - `--config-dir PATH`, defaulting to `config/`.
   - `--dry-run/--no-dry-run`, defaulting to `--no-dry-run`.
   - `--validation-only/--promote`, defaulting to `--validation-only` until export, import, retention, restore checks, and active `index_versions` promotion rules exist.
   - `--json`, returning machine-readable output.
3. Add `idp-brain ingest status` with options:
   - `--run-id UUID`, optional exact run lookup.
   - `--source-id TEXT`, optional source filter.
   - `--limit INTEGER`, default `10`.
   - `--json`, returning machine-readable output.
4. `ingest run` must create or reference an `ingestion_runs` record before fetch, discovery, extraction, embedding, or indexing work starts.
5. Keep scheduled and CI ingestion validation-only. The CLI may build inactive index versions, but it must not activate a new index version unless explicit promotion/export/import rules are implemented in a later step.
6. Print a Rich table by default with run ID, source ID, version/ref, status, started time, finished time, changed chunk count, failed chunk count, redacted chunk count, inactive index version, and validation-only flag.
7. Ensure all CLI output uses sanitized diagnostics only. Do not print raw source text, raw chunks, secret-looking values, PII, embedding vectors, SQL statements, or provider payloads.
8. Implement deterministic CI behavior by allowing tests to use fixture sources, a local temporary cache, mock embedding, and mock reranking. No external model or network call is required for command tests.
9. Add or update `mise run ingest` so it delegates to `idp-brain ingest run --validation-only` with repository defaults.

## Tests And Checks
- `uv run idp-brain ingest --help`
- `uv run idp-brain ingest run --help`
- `uv run idp-brain ingest status --help`
- `uv run pytest tests/cli/test_ingest_commands.py`
- `mise run ingest`
- `mise run ci`
- Tests must cover Rich output, `--json` output, dry-run behavior, validation-only default behavior, source filtering, status lookup, failure reporting, and absence of raw unsanitized chunk text in command output.

## Acceptance Criteria
- `idp-brain ingest run` starts a configured ingestion run and reports sanitized run metadata.
- `idp-brain ingest status` lists recent runs and can inspect a specific run.
- The default path is safe for CI and scheduled validation: no index promotion and no durable server database assumption.
- Local and CI tests pass with deterministic fixture data, mock embeddings, and mock reranking.
- Command output never exposes raw unsanitized chunks, secrets, PII, direct SQL access, vectors, or provider payloads.

## Suggested Commit Message
`feat: add ingestion cli commands`
