# 3.10: Ingestion Test Suite

## Goal
Add a focused ingestion test suite and CI coverage that verifies source listing, run recording, local and Git fetchers, artifact discovery, extraction, redaction, chunking, incremental updates, tombstones, and safety invariants end to end.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 3.1 through Phase 3.9 are complete.
- Phase 1 CI and `mise run ci` exist.
- Local Postgres migrations can recreate schema state from scratch.

## Files To Create Or Modify
- `tests/ingestion/test_sources_list.py`
- `tests/ingestion/test_ingestion_runs.py`
- `tests/ingestion/test_local_directory.py`
- `tests/ingestion/test_git_repository.py`
- `tests/ingestion/test_artifact_discovery.py`
- `tests/ingestion/test_extractors.py`
- `tests/ingestion/test_redaction_safety.py`
- `tests/ingestion/test_chunking.py`
- `tests/ingestion/test_incremental_tombstones.py`
- `tests/ingestion/test_end_to_end_sanitized_ingestion.py`
- `tests/fixtures/ingestion/`
- `tests/conftest.py`
- `mise.toml`
- `.github/workflows/ci.yaml`

## Implementation Instructions
1. Organize ingestion tests under `tests/ingestion/` while keeping any earlier step-specific tests either moved or imported so coverage is not duplicated unnecessarily.
2. Add deterministic fixtures for `local_directory`, local Git repositories, Markdown, HTML, JSON, YAML, TOML, OpenAPI, JSON Schema, text, tree-sitter source-code extraction, generated files, vendored files, secrets, PII, license files, changed files, and removed files.
3. Ensure Git fixture tests create repositories locally with `git init`, commits, branches, and tags using fixed `user.name`, `user.email`, `GIT_AUTHOR_DATE`, and `GIT_COMMITTER_DATE`. Do not require GitHub, forge APIs, credentials, or network access in CI.
4. Add a reusable database fixture that runs migrations against disposable local Postgres and cleans test data between tests.
5. Add safety assertions that search all ingestion-owned persisted text columns for fixture raw secret values and fail if any raw value is found.
6. Add log capture assertions for representative failure paths so raw unsanitized chunks, secrets, PII, credentials, and raw diffs do not appear in logs or diagnostics.
7. Add end-to-end tests that ingest fixtures through the public CLI or orchestration entry point and verify persisted records are sanitized, cited, labeled, and versioned.
8. Verify generated and vendored files are excluded by default and included only with explicit, auditable profile overrides.
9. Verify extractor and chunker outputs carry source ID, source version ID, artifact ID, locator, line range where available, extractor name and version, extractor profile, redaction status, visibility label, sensitivity class, access label, license policy label, and sanitized content hash.
10. Verify incremental ingestion updates counters, avoids duplicate unchanged chunks, and tombstones removed artifacts and chunks without deleting historical citation records.
11. Add or update `mise run test` and `mise run ci` so the ingestion suite runs locally and in GitHub Actions with the same commands.
12. Keep scheduled ingestion validation out of scope. GitHub Actions should use ephemeral databases and fixture sources only until export/import, encryption, retention, restore checks, and index promotion are implemented later.

## Tests And Checks
- `mise run up`
- `mise run db:migrate`
- `mise run test`
- `mise run ci`
- Passing condition: the full ingestion suite passes locally and in CI using only fixture data, local Git repositories, deterministic scanners, and disposable Postgres.

## Acceptance Criteria
- Phase 3 has regression coverage for every ingestion stage and safety invariant.
- CI does not depend on external source services, external security scanners, external embedding providers, or durable databases.
- Tests fail if raw unsanitized chunks, fixture secrets, PII, credentials, or raw diffs are persisted, embedded, logged, returned, or placed in evaluation or LLM-facing data paths.
- Tests prove persisted records carry source, access, visibility, sensitivity, license policy, redaction status, citation, version, and sanitized content hash metadata.
- The ingestion suite is runnable through documented `mise` tasks.

## Suggested Commit Message
`test: add ingestion safety suite`
