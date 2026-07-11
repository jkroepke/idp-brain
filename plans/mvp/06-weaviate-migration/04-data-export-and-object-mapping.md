# 6.4: Sanitized Data Export And Object Mapping

## Goal

Map all required sanitized records from the temporary PostgreSQL source into the Weaviate collection model without carrying database-specific implementation details into the final application.

## Prerequisites

- Step 6.3 defines collection schemas and deterministic IDs.
- The PostgreSQL source contains only sanitized persistent evidence.
- A final pre-migration backup of the PostgreSQL source can be created.

## Files To Create Or Modify

- `src/idp_brain/migration/export_postgres.py`
- `src/idp_brain/migration/map_objects.py`
- `src/idp_brain/migration/manifest.py`
- migration-only CLI commands
- `mise.toml`
- migration fixtures and tests

## Data To Migrate

- sources and source versions
- active artifacts and sanitized chunks
- citation locators and provenance
- version membership and lineage fields
- claims and conflict markers when implemented
- relationships required by structured retrieval
- promoted memory items and safe memory links
- evaluation cases and results needed for regression history
- active index and model metadata required to explain the baseline

Operational SQL internals, extension metadata, Alembic state, database connection details, and raw provider payloads are not migrated.

## Implementation Instructions

1. Create a migration-only exporter that reads with bounded server-side batches and never loads the whole corpus into memory.
2. Export only records that passed redaction and corpus persistence policy.
3. Fail if an active chunk lacks required provenance, citation, policy, or sanitized content hash fields.
4. Map normalized relational records into the denormalized `EvidenceChunk` shape.
5. Preserve stable public IDs used by CLI and MCP fetch operations. Map them to deterministic Weaviate UUIDs.
6. Preserve source, version, path, line range, commit, tag, checksum, authority, freshness, visibility, sensitivity, license, and redaction metadata.
7. Convert relationship and lineage data into:
   - denormalized retrieval fields where needed by the main query.
   - optional references or structured collections for bounded navigation.
8. Do not migrate raw source caches, raw chunks, secrets, PII removed by redaction, SQL text, vectors by default, or provider request and response payloads.
9. Produce a migration manifest with:
   - source database snapshot identifier.
   - export timestamp.
   - object counts by target collection and content kind.
   - content-hash aggregates.
   - mapping version.
   - rejected record count and reasons.
10. Keep the manifest free of source content and credentials.
11. Prefer streaming directly to the importer. An intermediate JSONL or Parquet export is optional for audit and retry, must contain sanitized data only, and must be ignored by Git.
12. Make mapping functions pure and independently testable.
13. Add a `mise run migration:export-postgres` task used only during Phase 6.

## Tests And Checks

- Export deterministic fixtures twice and compare manifests.
- Verify object counts and content hashes match the source fixtures.
- Verify rejected records fail the migration unless explicitly allowlisted with a documented reason.
- Verify no raw secret fixture or unsanitized field appears in exported objects or manifests.
- Verify stable citation and chunk IDs are preserved.
- `mise run ci`

## Acceptance Criteria

- Every required persistent domain object has a documented Weaviate mapping.
- Export is bounded, deterministic, restartable, and sanitized.
- Counts and content hashes make omissions detectable.
- Database-specific operational records are not carried into Weaviate.
- Mapping code is clearly migration-only.

## Suggested Commit Message

`feat: map postgres data to weaviate`
