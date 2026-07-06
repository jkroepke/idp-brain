# 3.2: Ingestion Run Recording

## Goal
Create ingestion run records before any fetch, local filesystem scan, or extraction work begins, and update those records with deterministic status, diagnostics, and counts as the ingestion pipeline advances.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 2 data model steps are complete, including `sources`, `source_versions`, `ingestion_runs`, access policy models, and redaction/license metadata models.
- Phase 3.1 is complete so source definitions can be loaded and validated.
- Local Postgres starts through `mise run up`, and migrations run through `mise run db:migrate`.

## Files To Create Or Modify
- `src/idp_brain/cli.py`
- `src/idp_brain/ingestion/__init__.py`
- `src/idp_brain/ingestion/runs.py`
- `src/idp_brain/ingestion/pipeline.py`
- `src/idp_brain/models/ingestion.py`
- `src/idp_brain/repositories/ingestion_runs.py`
- `migrations/versions/<next>_ingestion_run_status_fields.py`
- `tests/test_ingestion_run_recording.py`
- `tests/fixtures/config/sources_valid.yaml`

## Implementation Instructions
1. Add an ingestion orchestration entry point that can start a run for one source ID or all enabled sources from `config/sources.yaml`.
2. Ensure the first durable action is inserting an `ingestion_runs` row with `status = "started"` before git commands, HTTP requests, local directory walks, discovery, extraction, redaction, chunking, embedding job creation, or retrieval indexing.
3. Store run metadata: run ID, source ID, requested ref or version selector, started timestamp, operator or caller label when available, config file hash, extractor profile name, visibility label, sensitivity class, license policy label, and access policy label.
4. Track status transitions with explicit values such as `started`, `fetching`, `discovering`, `extracting`, `redacting`, `chunking`, `persisting`, `completed`, and `failed`.
5. Record counters for fetched artifacts, discovered artifacts, extracted artifacts, redacted candidates, persisted sanitized chunks, skipped generated files, skipped vendored files, failed artifacts, and tombstoned records.
6. Store failure diagnostics as sanitized structured data with error type, stage, source ID, artifact locator when safe, and retryable flag; do not store raw upstream text, raw chunks, raw secret values, or full sensitive config values.
7. Add a minimal `idp-brain ingest run --source <source_id> --dry-run` path that creates and completes a run without fetching source content; this gives CI a deterministic command path before later fetchers exist.
8. If a later stage fails, update the run status to `failed` in a `finally` or transaction-safe error path and preserve the original run record.
9. Keep scheduled or remote ingestion out of scope; this step only records local CLI-driven runs.

## Tests And Checks
- `mise run up`
- `mise run db:migrate`
- `uv run idp-brain ingest run --source fixture-local-docs --config tests/fixtures/config/sources_valid.yaml --dry-run`
- `uv run pytest tests/test_ingestion_run_recording.py`
- `mise run test`
- Passing condition: a run row exists before any mocked fetch call is invoked, dry-run produces deterministic counters, failure paths mark the run failed, and diagnostics contain no raw fixture secret values.

## Acceptance Criteria
- Every ingestion attempt creates an `ingestion_runs` record before external or local source work begins.
- Run metadata carries source, access, visibility, sensitivity, and license policy labels.
- Status, counters, timestamps, and sanitized diagnostics are updated predictably.
- Failed runs are durable and inspectable without exposing raw unsanitized chunks or secret values.
- CI can exercise the run lifecycle with `--dry-run` and fixture configuration only.

## Suggested Commit Message
`feat: record ingestion runs before fetch`
