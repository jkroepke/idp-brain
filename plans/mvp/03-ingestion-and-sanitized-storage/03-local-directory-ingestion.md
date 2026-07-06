# 3.3: Local Directory Ingestion

## Goal
Implement `local_directory` source fetching as a deterministic local snapshot path that records source versions and artifact candidates without requiring network access or persisting raw unsanitized chunks.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 3.1 and Phase 3.2 are complete.
- Phase 2 models for `sources`, `source_versions`, `artifacts`, and `artifact_versions` exist.
- The test suite can run against a disposable local Postgres database.

## Files To Create Or Modify
- `src/idp_brain/ingestion/fetchers/__init__.py`
- `src/idp_brain/ingestion/fetchers/base.py`
- `src/idp_brain/ingestion/fetchers/local_directory.py`
- `src/idp_brain/ingestion/source_snapshot.py`
- `src/idp_brain/repositories/source_versions.py`
- `src/idp_brain/repositories/artifacts.py`
- `config/sources.yaml`
- `tests/fixtures/local_directory/docs/index.md`
- `tests/fixtures/local_directory/docs/reference.json`
- `tests/fixtures/local_directory/docs/secret-example.txt`
- `tests/test_local_directory_ingestion.py`

## Implementation Instructions
1. Add a `SourceFetcher` protocol with a `fetch(source, run) -> SourceSnapshot` method that returns metadata and artifact locators, not raw persisted content.
2. Implement `LocalDirectoryFetcher` for `source_type: local_directory`.
3. Require configured local paths to be explicit, normalized, and inside either the repository test fixtures or an operator-configured allowlist; reject path traversal and implicit home-directory expansion in source configuration.
4. Compute a deterministic source version for the snapshot from source ID, a stable configured root identifier or repository-relative fixture path, include/exclude configuration, and artifact content hashes. Use a stable hash such as SHA-256, and do not include machine-specific absolute temp or workspace paths in the source version hash.
5. Walk files in sorted path order so local and CI output is stable.
6. Record `source_versions`, `artifacts`, and `artifact_versions` with path, logical locator, checksum, size, mtime when useful, source type, visibility label, sensitivity class, license policy label, access policy label, first seen timestamp, and last verified timestamp.
7. Read file bytes only as needed to compute checksums and later extraction input; do not persist raw file content in Postgres, logs, diagnostics, or JSON command output.
8. Apply source-level include and exclude globs before artifact records are inserted, and preserve skip reasons in sanitized diagnostics.
9. Keep generated, vendored, extraction, redaction, chunking, and embedding behavior for later steps; this step only snapshots local artifacts and records safe metadata.

## Tests And Checks
- `mise run up`
- `mise run db:migrate`
- `uv run idp-brain ingest run --source fixture-local-docs --config tests/fixtures/config/sources_valid.yaml`
- `uv run pytest tests/test_local_directory_ingestion.py`
- `mise run test`
- Passing condition: fixture files are recorded as artifacts in deterministic order, the same fixture produces the same source version hash across repeated runs, excluded paths are skipped with sanitized reasons, and the raw contents of `secret-example.txt` are not present in database text columns or logs.

## Acceptance Criteria
- `local_directory` sources can be ingested without network access.
- Artifact and source version records carry access, visibility, sensitivity, and license policy labels.
- Local fixture ingestion is deterministic in CI.
- Raw unsanitized file content is never persisted, embedded, logged, returned, or included in diagnostics.
- The implementation creates safe artifact candidates for later discovery, extraction, redaction, and chunking steps.

## Suggested Commit Message
`feat: add local directory ingestion`
