# MVP Implementation Plan

This README is the operating guide for the `idp-brain` MVP.

## Current State

Phases 1 through 4 and Step 5.1 were implemented with PostgreSQL, ParadeDB, pgvector, SQLAlchemy, application-owned retrieval fusion, and a planned custom MCP server.

The target architecture changed before the MVP was released. The project does not need to preserve a production database. Searchable state is reproducible from configured sources.

Starting with Step 5.2, the plan performs a destructive Weaviate architecture reset:

- preserve source acquisition, extraction, redaction, chunking, deterministic identity, CLI structure, and reusable evaluation fixtures
- replace the complete persistence and retrieval back half
- use one versioned Weaviate `EvidenceChunk` collection
- use direct Weaviate hybrid search
- use Weaviate's built-in read-only MCP server
- rebuild from sources rather than migrate PostgreSQL rows
- remove the legacy database and retrieval stack after the vertical slice passes

## MVP Goal

Build a local-first Python 3.14 pipeline that ingests configured technical sources, persists only sanitized evidence in Weaviate, and exposes that evidence through a thin CLI and Weaviate's built-in read-only MCP server.

## Execution Rules

- Complete steps in order.
- Keep one focused commit per step.
- Run every listed test and check.
- Never persist, vectorize, log, trace, profile, or return raw unsanitized source content.
- Do not add new features to the PostgreSQL implementation.
- Do not build a PostgreSQL export, dual-write, compatibility, or rollback framework.
- Rebuild Weaviate from configured sources.
- Prefer Weaviate-native features over new application abstractions.
- Do not recreate the former relational schema as many Weaviate collections.
- Do not implement an application-owned MCP server unless a measured requirement cannot be met by Weaviate MCP, RBAC, tenants, collection design, and returned properties.
- Keep CI deterministic and independent from paid external providers.

## Phase Overview

- **Phases 1–4:** implemented legacy baseline; retained only as code to reuse or delete.
- **Step 5.1:** implemented ingest CLI surface.
- **Steps 5.2–5.9:** Weaviate architecture reset.
- **Phase 6:** Day-2 operations and OpenTelemetry.

## Phase 1: Skeleton And Local Runtime

- [Phase directory](01-skeleton-and-local-runtime/)
- [1.1 Python Project Scaffold](01-skeleton-and-local-runtime/01-python-project-scaffold.md)
- [1.2 Mise Task Runner](01-skeleton-and-local-runtime/02-mise-task-runner.md)
- [1.3 Lint Type Test Tooling](01-skeleton-and-local-runtime/03-lint-type-test-tooling.md)
- [1.4 Docker Compose Postgres](01-skeleton-and-local-runtime/04-docker-compose-postgres.md)
- [1.5 Pydantic Settings And Env Example](01-skeleton-and-local-runtime/05-pydantic-settings-and-env-example.md)
- [1.6 Alembic Base And Extension Migration](01-skeleton-and-local-runtime/06-alembic-base-and-extension-migration.md)
- [1.7 Extension Smoke Test](01-skeleton-and-local-runtime/07-extension-smoke-test.md)
- [1.8 GitHub Actions CI](01-skeleton-and-local-runtime/08-github-actions-ci.md)

## Phase 2: Configuration And Core Data Model

- [Phase directory](02-configuration-and-data-model/)
- [2.1 Config Loader Models](02-configuration-and-data-model/01-config-loader-models.md)
- [2.2 Example Config Files](02-configuration-and-data-model/02-example-config-files.md)
- [2.3 Core SQLAlchemy Models](02-configuration-and-data-model/03-core-sqlalchemy-models.md)
- [2.4 Corpus Eligibility Policy Models](02-configuration-and-data-model/04-corpus-eligibility-policy-models.md)
- [2.5 Redaction And License Models](02-configuration-and-data-model/05-redaction-and-license-models.md)
- [2.6 Index Versions And Embedding Jobs](02-configuration-and-data-model/06-index-versions-and-embedding-jobs.md)
- [2.7 DB Mise Tasks](02-configuration-and-data-model/07-db-mise-tasks.md)
- [2.8 Model And Migration Tests](02-configuration-and-data-model/08-model-and-migration-tests.md)

## Phase 3: Generic Ingestion And Sanitized Storage

- [Phase directory](03-ingestion-and-sanitized-storage/)
- [3.1 Sources List Command](03-ingestion-and-sanitized-storage/01-sources-list-command.md)
- [3.2 Ingestion Run Recording](03-ingestion-and-sanitized-storage/02-ingestion-run-recording.md)
- [3.3 Local Directory Ingestion](03-ingestion-and-sanitized-storage/03-local-directory-ingestion.md)
- [3.4 Git Repository Fetcher](03-ingestion-and-sanitized-storage/04-git-repository-fetcher.md)
- [3.5 Artifact Discovery](03-ingestion-and-sanitized-storage/05-artifact-discovery.md)
- [3.6 Extractor Interfaces And Basic Extractors](03-ingestion-and-sanitized-storage/06-extractor-interfaces-and-basic-extractors.md)
- [3.7 Redaction Before Persistence](03-ingestion-and-sanitized-storage/07-redaction-before-persistence.md)
- [3.8 Structure Aware Chunking](03-ingestion-and-sanitized-storage/08-structure-aware-chunking.md)
- [3.9 Incremental Ingestion And Tombstones](03-ingestion-and-sanitized-storage/09-incremental-ingestion-and-tombstones.md)
- [3.10 Ingestion Test Suite](03-ingestion-and-sanitized-storage/10-ingestion-test-suite.md)

## Phase 4: Legacy Retrieval Baseline

This phase is already implemented. Its PostgreSQL, ParadeDB, pgvector, RRF, reranker, and evidence-bundle code is removed during Step 5.8 rather than ported.

- [Phase directory](04-embeddings-bm25-pgvector-retrieval/)
- [4.1 Embedding Provider Interface](04-embeddings-bm25-pgvector-retrieval/01-embedding-provider-interface.md)
- [4.2 Embedding Jobs And Vector Storage](04-embeddings-bm25-pgvector-retrieval/02-embedding-jobs-and-vector-storage.md)
- [4.3 ParadeDB BM25 Migration](04-embeddings-bm25-pgvector-retrieval/03-paradedb-bm25-migration.md)
- [4.4 pgvector HNSW Migration](04-embeddings-bm25-pgvector-retrieval/04-pgvector-hnsw-migration.md)
- [4.5 Exact Lookup Retrieval](04-embeddings-bm25-pgvector-retrieval/05-exact-lookup-retrieval.md)
- [4.6 BM25 Candidate Retrieval](04-embeddings-bm25-pgvector-retrieval/06-bm25-candidate-retrieval.md)
- [4.7 Vector Candidate Retrieval](04-embeddings-bm25-pgvector-retrieval/07-vector-candidate-retrieval.md)
- [4.8 Query Profiles](04-embeddings-bm25-pgvector-retrieval/08-query-profiles.md)
- [4.9 Corpus Eligibility Filtering Before Subqueries](04-embeddings-bm25-pgvector-retrieval/09-corpus-eligibility-filtering-before-subqueries.md)
- [4.10 Reciprocal Rank Fusion](04-embeddings-bm25-pgvector-retrieval/10-reciprocal-rank-fusion.md)
- [4.11 Reranker Interface](04-embeddings-bm25-pgvector-retrieval/11-reranker-interface.md)
- [4.12 Evidence Bundle Contract](04-embeddings-bm25-pgvector-retrieval/12-evidence-bundle-contract.md)
- [4.13 Retrieval Test Suite](04-embeddings-bm25-pgvector-retrieval/13-retrieval-test-suite.md)

## Phase 5: Weaviate Architecture Reset

- [Phase directory](05-cli-mcp-evaluation-operations/)
- [5.1 Ingest CLI Commands](05-cli-mcp-evaluation-operations/01-ingest-cli-commands.md)
- [5.2 Weaviate Vertical Slice](05-cli-mcp-evaluation-operations/02-weaviate-vertical-slice.md)
- [5.3 Weaviate Runtime And Collection](05-cli-mcp-evaluation-operations/03-weaviate-runtime-and-collection.md)
- [5.4 Replace Ingestion Persistence](05-cli-mcp-evaluation-operations/04-weaviate-ingestion-store.md)
- [5.5 Direct Weaviate Retrieval CLI](05-cli-mcp-evaluation-operations/05-weaviate-retrieval-cli.md)
- [5.6 Built-In Weaviate MCP Server](05-cli-mcp-evaluation-operations/06-weaviate-built-in-mcp.md)
- [5.7 Adapt Evaluation To Weaviate](05-cli-mcp-evaluation-operations/07-weaviate-evaluation.md)
- [5.8 Remove The Legacy Stack](05-cli-mcp-evaluation-operations/08-remove-legacy-stack.md)
- [5.9 Clean-Checkout Completion Gate](05-cli-mcp-evaluation-operations/09-clean-checkout-completion-gate.md)

## Phase 6: Day-2 Operations And OpenTelemetry

- [Phase directory](06-day-2-operations/)
- [6.1 Observability Backend Stack](06-day-2-operations/01-otel-backend-stack.md)
- [6.2 OpenTelemetry Metrics And Weaviate Monitoring](06-day-2-operations/02-otel-metrics.md)
- [6.3 OpenTelemetry Logging](06-day-2-operations/03-otel-logging.md)
- [6.4 OpenTelemetry Traces](06-day-2-operations/04-otel-traces.md)
- [6.5 Weaviate Backup And Restore](06-day-2-operations/05-weaviate-backup.md)
- [6.6 OpenTelemetry Span Profiling](06-day-2-operations/06-otel-profiling.md)
- [6.7 Python 3.14 Free-Threaded Integration Test](06-day-2-operations/07-free-threaded-integration-test.md)
