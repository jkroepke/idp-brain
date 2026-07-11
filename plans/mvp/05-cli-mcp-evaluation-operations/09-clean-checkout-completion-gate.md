# 5.9: Clean-Checkout Completion Gate

## Goal

Prove the complete MVP retrieval path from an empty environment and disposable Weaviate volume.

## Test Flow

1. install pinned tools and dependencies
2. start Weaviate
3. bootstrap the versioned collection
4. ingest deterministic fixture sources
5. rerun ingestion and verify idempotent object identity
6. run BM25-only, vector-only, and hybrid queries through the Python client
7. query the same collection through built-in MCP
8. verify sanitized content and citation properties
9. run evaluation and thresholds
10. delete the Weaviate volume
11. rebuild the complete searchable state from source configuration
12. rerun retrieval and evaluation
13. tear down resources even after failure

## Required Assertions

- no PostgreSQL, ParadeDB, SQLAlchemy, Alembic, psycopg, pgvector, RRF, custom reranker, evidence-bundle, or custom MCP path is imported
- write access through MCP is disabled
- citation metadata survives rebuild
- no unsanitized fixture value appears in storage, output, logs, traces, or profiles
- CI does not require external paid providers
- `mise run ci`

## Acceptance Criteria

A clean checkout can recreate and query the whole knowledge index using only configured sources, Python, and Weaviate.
