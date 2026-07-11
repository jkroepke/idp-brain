# MVP Implementation Plan

This README is the operating guide for the `idp-brain` MVP plan. Follow the steps in order and treat every step file as an implementation contract.

## MVP Goal

Build a local-first Python 3.14 retrieval pipeline that ingests configured technical sources, persists only sanitized evidence, and exposes citation-backed retrieval through CLI and read-only MCP tools.

Phases 1 through 5 establish and evaluate the original PostgreSQL, ParadeDB, and pgvector implementation. Phase 6 uses that measured baseline to migrate the complete knowledge and retrieval path to Weaviate. After the cutover, Weaviate is the only required persistent store and owns object storage, vectorization, BM25F, vector indexing, metadata filtering, and hybrid fusion.

The MVP is complete when ingestion, exact and hybrid retrieval, evidence bundles, MCP tools, evaluation, the Weaviate migration, CI, the local observability stack, OpenTelemetry instrumentation, Weaviate monitoring, continuous profiling, backup and restore, and Python 3.14 free-threaded validation work together.

## Execution Rules

- Complete steps in order.
- Keep one focused commit per step.
- Run every listed test and check.
- Do not persist, vectorize, log, or return raw unsanitized chunks.
- Apply source, license, sensitivity, redaction, version, active-state, and collection-generation filters to every retrieval request.
- Keep CI deterministic and independent from paid or private external services.
- Treat caller-provided MCP context only as a hint. Trusted corpus eligibility is derived server-side.
- Do not invent version lineage or citations.
- During Phase 6, keep the old retrieval path only as a migration oracle. Do not add new features to it.
- After Phase 6, do not retain PostgreSQL, ParadeDB, pgvector, SQLAlchemy, Alembic, or psycopg as runtime dependencies.

## Phase Overview

Phase 1 establishes the Python project, task runner, local PostgreSQL runtime, migrations, extension checks, and CI baseline.

Phase 2 defines configuration, corpus policy, redaction, licensing, indexing, and relational data models.

Phase 3 implements source ingestion, extraction, redaction-before-persistence, structure-aware chunking, incremental updates, and tombstones.

Phase 4 implements embeddings, ParadeDB BM25, pgvector, exact lookup, corpus filtering, fusion, reranking, evidence bundles, and retrieval tests.

Phase 5 exposes the system through CLI and read-only MCP tools and adds retrieval evaluation, thresholds, and deterministic GitHub Actions evaluation.

Phase 6 migrates all persistent knowledge and retrieval responsibilities from PostgreSQL, ParadeDB, and pgvector to Weaviate. It defines collections and deterministic IDs, backfills sanitized data, moves vectorization and hybrid search into Weaviate, validates a shadow path, cuts over CLI and MCP, and removes the old database stack.

Phase 7 contains day-2 operations: the complete local observability stack, OpenTelemetry metrics, logs and traces, Weaviate metrics, OpenTelemetry-correlated continuous profiling, Weaviate backup and restore, and a final Python 3.14 free-threaded integration test with the global interpreter lock disabled.

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

## Phase 4: Embeddings, BM25, pgvector, And Retrieval

This phase remains the measurable migration baseline. Do not extend it after Phase 6 starts.

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

## Phase 5: CLI, MCP, Evaluation, And CI

- [Phase directory](05-cli-mcp-evaluation-operations/)
- [5.1 Ingest CLI Commands](05-cli-mcp-evaluation-operations/01-ingest-cli-commands.md)
- [5.2 Retrieve Query Command](05-cli-mcp-evaluation-operations/02-retrieve-query-command.md)
- [5.3 Retrieve Explain Command](05-cli-mcp-evaluation-operations/03-retrieve-explain-command.md)
- [5.4 MCP Stdio Server](05-cli-mcp-evaluation-operations/04-mcp-stdio-server.md)
- [5.5 MCP Search Tool](05-cli-mcp-evaluation-operations/05-mcp-search-tool.md)
- [5.6 MCP Fetch Tool](05-cli-mcp-evaluation-operations/06-mcp-fetch-tool.md)
- [5.7 MCP Explain And List Sources](05-cli-mcp-evaluation-operations/07-mcp-explain-and-list-sources.md)
- [5.8 Eval Run Command](05-cli-mcp-evaluation-operations/08-eval-run-command.md)
- [5.9 Evaluation Metrics](05-cli-mcp-evaluation-operations/09-evaluation-metrics.md)
- [5.10 Evaluation Thresholds And CI Gates](05-cli-mcp-evaluation-operations/10-evaluation-thresholds-and-ci-gates.md)
- [5.13 GitHub Actions Eval](05-cli-mcp-evaluation-operations/13-github-actions-eval.md)

## Phase 6: Migrate From ParadeDB To Weaviate

Phase 6 treats the existing PostgreSQL implementation as a temporary source and regression oracle. The target has one persistent store: Weaviate.

- [Phase directory](06-weaviate-migration/)
- [6.1 Architecture Decision And Migration Guardrails](06-weaviate-migration/01-architecture-decision-and-guardrails.md)
- [6.2 Weaviate Runtime And Dependency Replacement](06-weaviate-migration/02-runtime-and-dependencies.md)
- [6.3 Collection Schema And Deterministic IDs](06-weaviate-migration/03-collections-and-deterministic-ids.md)
- [6.4 Sanitized Data Export And Object Mapping](06-weaviate-migration/04-data-export-and-object-mapping.md)
- [6.5 Batch Import, Vectorization, And Index Build](06-weaviate-migration/05-batch-import-vectorization-and-indexes.md)
- [6.6 Hybrid, Exact, And Structured Retrieval](06-weaviate-migration/06-retrieval-cutover.md)
- [6.7 Corpus Eligibility, Citations, And Evidence Bundles](06-weaviate-migration/07-policy-citations-and-evidence.md)
- [6.8 Shadow Evaluation And Relevance Parity](06-weaviate-migration/08-shadow-evaluation.md)
- [6.9 Cutover, Backup, Restore, And Rollback](06-weaviate-migration/09-cutover-backup-and-rollback.md)
- [6.10 Remove PostgreSQL, ParadeDB, And pgvector](06-weaviate-migration/10-remove-postgres-stack.md)
- [6.11 Migration Test Suite And Completion Gate](06-weaviate-migration/11-migration-test-suite.md)

## Phase 7: Day-2 Operations And OpenTelemetry

Application metrics, logs, and traces use OpenTelemetry APIs and OTLP. Grafana Alloy receives application telemetry and scrapes Weaviate's Prometheus-compatible metrics. Continuous Python profiles are linked to OpenTelemetry root spans with `pyroscope-otel` and routed through Alloy to Pyroscope.

- [Phase directory](07-day-2-operations/)
- [7.1 OpenTelemetry Backend Stack](07-day-2-operations/01-otel-backend-stack.md)
- [7.2 OpenTelemetry Metrics And Weaviate Monitoring](07-day-2-operations/02-otel-metrics.md)
- [7.3 OpenTelemetry Logging](07-day-2-operations/03-otel-logging.md)
- [7.4 OpenTelemetry Traces](07-day-2-operations/04-otel-traces.md)
- [7.5 Weaviate Backup And Restore](07-day-2-operations/05-weaviate-backup.md)
- [7.6 OpenTelemetry Span Profiling](07-day-2-operations/06-otel-profiling.md)
- [7.7 Python 3.14 Free-Threaded Integration Test](07-day-2-operations/07-free-threaded-integration-test.md)
