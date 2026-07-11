# 5.4: Replace Ingestion Persistence

## Goal

Keep the existing ingestion front half and replace SQLAlchemy repositories with direct, idempotent Weaviate batch writes.

## Instructions

1. Preserve source configuration, fetching, discovery, extraction, redaction, chunking, and deterministic identity.
2. Define a small Pydantic `EvidenceChunk` write model containing sanitized content and citation properties.
3. Add a narrow Weaviate batch writer. Avoid a generic repository framework.
4. Use deterministic UUIDs so rerunning the same source version replaces the same logical objects.
5. Report failed batch object IDs and retry safely.
6. Adapt `idp-brain ingest run` to write directly to the selected collection generation.
7. Keep validation-only behavior until promotion semantics are replaced.
8. Replace SQL-backed ingestion status with either:
   - bounded current-process results and structured telemetry, or
   - a small `IngestionRun` collection only when persisted history is required.
9. Do not port embedding jobs, relational transactions, tombstone tables, or inactive-index rows.

## Checks

- ingestion unit tests continue to cover fetch, extraction, redaction, and chunking
- integration tests verify deterministic upsert and repeatability
- no unsanitized text reaches the client
- partial batch failures are bounded and retryable
- `mise run ingest`
- `mise run ci`

## Acceptance Criteria

The ingest CLI rebuilds sanitized evidence directly into Weaviate without SQLAlchemy, Alembic, PostgreSQL, embedding jobs, or a second persistence model.
