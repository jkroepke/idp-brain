# 5.8: Remove The Legacy Stack

## Goal

Delete the obsolete persistence, retrieval, evidence-bundle, reranker, and MCP implementation after the Weaviate vertical path and evaluation pass.

## Remove

- PostgreSQL and ParadeDB Compose services
- PostgreSQL volumes, health checks, and environment settings
- SQLAlchemy, Alembic, psycopg, pgvector, and ParadeDB dependencies
- `migrations/`
- ORM models used only for persistence
- SQL repository implementations
- embedding jobs and stored vectors
- exact, BM25, and vector SQL retrievers
- reciprocal rank fusion
- default application reranker registry and mock
- SQL-backed evidence-bundle assembly
- custom MCP server and tools
- database backup, reset, migrate, and check tasks
- PostgreSQL integration tests
- tests that validate removed implementation details
- PostgreSQL-specific OpenTelemetry instrumentation and metrics receiver configuration

## Preserve

- reusable source and extractor configuration
- fetchers, discovery, extraction, redaction, and chunking
- deterministic identity helpers that remain useful
- sanitized CLI behavior
- Weaviate integration and behavioral evaluation tests

## Checks

- dependency and import searches find no runtime PostgreSQL stack
- no custom MCP server remains
- no RRF or legacy retrieval path remains
- Docker Compose contains Weaviate as the only persistent application service
- `uv lock` is regenerated
- `mise run ci`

## Acceptance Criteria

The repository contains one active persistence and retrieval architecture, not a deprecated compatibility layer.
