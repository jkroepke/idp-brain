# 6.1: Architecture Decision And Migration Guardrails

## Goal

Record Weaviate as the long-term knowledge and retrieval platform and define the boundaries for migrating away from PostgreSQL, ParadeDB `pg_search`, and pgvector.

## Decision

After Phase 6, Weaviate is the only required persistent store.

The existing PostgreSQL implementation is treated as a temporary migration source and evaluation oracle. Existing implementation effort is not a reason to keep it. The decision is based on reducing long-term maintenance through one platform that owns object storage, vectorization, BM25F, vector indexes, metadata filters, and hybrid fusion.

## Prerequisites

- Phases 1 through 5 are complete enough to provide deterministic ingestion and retrieval fixtures.
- Retrieval evaluation thresholds exist or are recorded as diagnostics.
- Only sanitized evidence is present in the migration source.
- `ARCHITECTURE.md` describes Weaviate as the target architecture.

## Files To Create Or Modify

- `ARCHITECTURE.md`
- `plans/mvp/README.md`
- `docs/adr/` or the repository's architecture decision location
- `config/retrieval.yaml`
- `config/evaluation.yaml`

## Implementation Instructions

1. Add an architecture decision that explicitly selects Weaviate as the target persistent knowledge and retrieval store.
2. State that sunk implementation cost in PostgreSQL does not influence the target architecture.
3. Freeze new feature work on the PostgreSQL, ParadeDB, and pgvector retrieval path. Only migration fixes and regression instrumentation are allowed.
4. Define the final ownership boundary:
   - Weaviate owns persistent objects, vectors, BM25F, vector indexes, metadata filtering, and hybrid fusion.
   - the application owns extraction, redaction, deterministic IDs, corpus eligibility, citations, evidence bundles, and evaluation.
5. Define the removal target:
   - PostgreSQL service.
   - ParadeDB `pg_search`.
   - pgvector.
   - SQLAlchemy.
   - Alembic.
   - psycopg and psycopg2.
   - database migrations and SQL-specific retrieval adapters.
6. Define the migration safety rules:
   - never export or import raw unsanitized content.
   - keep deterministic object IDs.
   - support idempotent re-runs.
   - validate every imported object count and content hash.
   - keep a rollback path until Weaviate passes the completion gate.
   - do not silently drop citations, source versions, policy labels, claims, relationships, or memory.
7. Define the migration baseline from the Phase 5 evaluation suite. The goal is not score equality; the goal is equal or better held-out retrieval quality and preserved safety behavior.
8. Define one feature flag or configuration switch for the temporary shadow period. Do not introduce a permanent multi-backend abstraction.
9. Define the final cutover condition: CLI, MCP, ingestion, evaluation, and operations work without a PostgreSQL connection string.
10. Record known Weaviate tradeoffs that the application must handle:
    - no cross-object relational transaction boundary.
    - schema and vectorizer changes may require a new collection generation.
    - references are not a replacement for denormalized retrieval metadata.
    - deterministic CI must not depend on paid vectorizer APIs.

## Tests And Checks

- Review the architecture and migration decision for contradictory PostgreSQL target statements.
- Verify the migration completion criteria are measurable.
- Verify each removed dependency has a later removal step.
- Verify the Phase 5 retrieval suite can run before migration work begins.
- `mise run ci`

## Acceptance Criteria

- Weaviate is the unambiguous target architecture.
- The old retrieval path is frozen except for migration support.
- Ownership boundaries and removal targets are explicit.
- Safety, rollback, and evaluation gates are documented.
- No permanent dual-store architecture is planned.

## Suggested Commit Message

`docs: select weaviate as retrieval platform`
