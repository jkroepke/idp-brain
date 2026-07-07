# 3.9: Incremental Ingestion And Tombstones

## Goal
Detect unchanged, changed, added, and removed artifacts and chunks across ingestion runs, persist only changed sanitized records, and tombstone records that are no longer present without guessing version lineage.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 3.8 is complete.
- Phase 2 models include version membership tables such as `artifact_versions`, `chunk_versions`, `fact_versions`, `claim_versions`, and relationship version tables or their MVP subset.
- Fetchers provide source version IDs, checksums, and artifact locators for local directory and Git sources.

## Files To Create Or Modify
- `src/idp_brain/ingestion/incremental.py`
- `src/idp_brain/ingestion/tombstones.py`
- `src/idp_brain/repositories/artifact_versions.py`
- `src/idp_brain/repositories/chunk_versions.py`
- `src/idp_brain/repositories/fact_versions.py`
- `src/idp_brain/repositories/claim_versions.py`
- `src/idp_brain/repositories/relationships.py`
- `migrations/versions/<next>_incremental_membership_fields.py`
- `tests/fixtures/incremental/v1/`
- `tests/fixtures/incremental/v2/`
- `tests/test_incremental_ingestion_and_tombstones.py`

## Implementation Instructions
1. Add an incremental planning stage that compares the current fetched artifact set with the latest successful run for the same source and version strategy.
2. Compare artifacts by stable locator and raw artifact checksum for fetch-level change detection, but persist only checksums and metadata, not raw content.
3. Compare chunks by sanitized content hash, chunker profile, structure path, and artifact locator so redaction and chunking changes create new chunk versions predictably.
4. Skip extraction, redaction, and chunking for unchanged artifacts when extractor profile, redaction rule version, chunker profile, and relevant source metadata are unchanged.
5. Reprocess artifacts when raw checksum, extractor version, extractor profile, redaction rule version, license policy version, sensitivity policy version, or chunker profile changes.
6. Write `first_seen`, `last_seen`, `first_verified`, `last_verified`, `first_containing_version`, and `last_containing_version` only when supported by evidence from the current source version, Git ancestry, tag map, or local snapshot comparison.
7. When an artifact, chunk, fact, claim, or relationship disappears from the current source version, mark the membership inactive or tombstoned with `last_seen` or `last_containing_version` where known. Do not delete historical rows needed for citations and lineage.
8. Keep unknown lineage unknown. Do not infer that a removed file was removed in a release unless Git ancestry or source version mapping proves it.
9. Generate embeddings only for changed sanitized chunks in later Phase 4 code. In this step, create deterministic pending indicators or counters only if the Phase 2 embedding job table already exists.
10. Carry source ID, source version ID, corpus eligibility label, visibility label, sensitivity class, license policy label, redaction status, and sanitized content hash onto version membership and tombstone records.
11. Update ingestion run counters for unchanged artifacts, changed artifacts, added artifacts, tombstoned artifacts, unchanged chunks, changed chunks, and tombstoned chunks.
12. Ensure tombstone diagnostics contain locators and sanitized hashes only, never raw removed content.

## Tests And Checks
- `mise run up`
- `mise run db:migrate`
- `uv run pytest tests/test_incremental_ingestion_and_tombstones.py`
- `mise run test`
- Passing condition: ingesting fixture `v1` then `v2` marks added, changed, unchanged, and removed artifacts and chunks deterministically; unchanged chunks are not duplicated; tombstoned records remain queryable by historical citation ID but inactive for current retrieval; unknown first/last version fields remain unknown when not proven.

## Acceptance Criteria
- Incremental ingestion avoids reprocessing unchanged artifacts when relevant profiles and policy versions are unchanged.
- Changed sanitized chunks receive new version membership without mutating historical evidence.
- Removed artifacts and chunks are tombstoned rather than hard deleted.
- Ingestion run counters and diagnostics explain incremental decisions without exposing raw content.
- License, source, corpus eligibility, visibility, sensitivity, redaction, and sanitized hash metadata remain attached to active and tombstoned records.

## Suggested Commit Message
`feat: add incremental ingestion tombstones`
