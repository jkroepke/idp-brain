# 6.2: OpenTelemetry Metrics

## Goal

Add OpenTelemetry metrics for ingestion, retrieval, evaluation, embedding jobs, redaction, candidate counts, latency, and PostgreSQL operations, exported through OTLP to the backend stack from Step 6.1.

## Prerequisites

- Step 6.1 has added the local OTLP gateway, metrics backend, and collector-native PostgreSQL receiver.
- Steps 5.1 through 5.10 and 5.13 have added ingest commands, retrieval commands, MCP tools, eval runs, thresholds, and CI evaluation.
- Retrieval events and ingestion runs expose sanitized counters and timings.
- Local runtime includes PostgreSQL and can enable `pg_stat_statements` for database statistics without exporting query text.
- `ARCHITECTURE.md` remains the source of truth for required metrics and operations tools.

## Files To Create Or Modify

- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/observability/__init__.py`
- `src/idp_brain/observability/metrics.py`
- `src/idp_brain/ingestion/orchestrator.py`
- `src/idp_brain/retrieval/service.py`
- `src/idp_brain/evaluation/runner.py`
- `src/idp_brain/settings.py`
- `config/observability/alloy.alloy`
- Database initialization or migration files for the telemetry monitoring role
- `tests/observability/test_otel_metrics.py`
- `tests/observability/test_metrics_redaction.py`
- `tests/integration/test_postgresql_receiver.py`

## Implementation Instructions

1. Configure the OpenTelemetry SDK `MeterProvider`, periodic metric reader, and OTLP exporter through application settings. Tests must use an isolated in-memory reader.
2. Define ingestion metrics:
   - `idp_brain_ingestion_runs_total`
   - `idp_brain_ingestion_changed_chunks_total`
   - `idp_brain_ingestion_failed_chunks_total`
   - `idp_brain_ingestion_redacted_chunks_total`
3. Define embedding metrics:
   - `idp_brain_embedding_jobs_total`
   - `idp_brain_embedding_job_failures_total`
4. Define retrieval latency histograms:
   - `idp_brain_retrieval_exact_latency_seconds`
   - `idp_brain_retrieval_bm25_latency_seconds`
   - `idp_brain_retrieval_vector_latency_seconds`
   - `idp_brain_retrieval_relationship_latency_seconds`
   - `idp_brain_retrieval_filtering_latency_seconds`
   - `idp_brain_retrieval_fusion_latency_seconds`
   - `idp_brain_retrieval_reranker_latency_seconds`
   - `idp_brain_retrieval_evidence_packaging_latency_seconds`
   - `idp_brain_retrieval_total_latency_seconds`
5. Define retrieval candidate counters or histograms for candidate counts before and after filtering, fusion, and reranking.
6. Define evaluation metrics for Recall@k, MRR, nDCG@10, hit rate, context precision, context recall, abstention correctness, threshold pass/fail counts, and diagnostic-only counts.
7. Use attributes such as route, tool, retrieval mode, query profile, source type, index version, redaction status, and outcome only when values are bounded or normalized. Do not use raw queries, source paths, citation IDs, chunk IDs, user-provided text, SQL, exception messages, or high-cardinality identifiers as attributes.
8. Export application metrics through OTLP only. Do not add an application scrape endpoint and do not expose metrics through MCP tools.
9. Configure PostgreSQL database metrics with Alloy's `otelcol.receiver.postgresql` component:
   - endpoint: the Docker Compose PostgreSQL service on port `5432`.
   - database allowlist: `idp_brain` only.
   - authentication: a dedicated monitoring role supplied through environment or secret configuration.
   - minimum permissions: `SELECT` on `pg_stat_database` and no read access to application source tables.
   - bounded collection interval, initial delay, and connection-pool settings where supported by the pinned build.
   - consistent `postgresql.schema.name` and `postgresql.table.name` resource attributes when the corresponding receiver feature gate is supported and tested.
10. Use the receiver's metrics output for database, connection, transaction, block, row, table, index, lock, replication, and WAL visibility where those metrics are supported by the pinned receiver version. Treat missing metrics as an explicit implementation gap rather than adding a separate backend-specific exporter.
11. Keep `db.server.query_sample` and `db.server.top_query` event collection disabled. Do not export statements, plans, bind values, or rows from `pg_stat_activity` or `pg_stat_statements`. Query-level observability in the MVP is aggregate and sanitized only.
12. Route PostgreSQL receiver metrics through the same OpenTelemetry processing and OTLP export path as the application metrics. Add resource attributes that distinguish the database service without introducing credentials, host-specific secrets, or unbounded names.
13. Propagate the same service resource attributes and correlation identifiers used by logs and traces.
14. Keep CI deterministic by testing instruments against an isolated in-memory reader. Run the PostgreSQL receiver integration test only in the local stack or an isolated CI service environment.

## Tests And Checks

- `uv run pytest tests/observability/test_otel_metrics.py tests/observability/test_metrics_redaction.py`
- `docker compose config`
- Start the local stack and run `tests/integration/test_postgresql_receiver.py`.
- Verify the receiver authenticates with the least-privilege monitoring role and cannot read application source tables.
- Verify expected PostgreSQL metric families reach the metrics backend with stable database, schema, table, and index attributes.
- Verify query sample and top-query events are disabled and no SQL text, query plan, bind value, or source row appears in telemetry.
- `mise run ci`
- Run one fixture ingestion, retrieval, and eval, then query the metrics backend through Grafana and confirm the expected application instrument names exist.
- Tests must cover counter increments, histogram recordings, PostgreSQL receiver configuration, bounded attributes, no raw query attributes, no raw chunk attributes, no SQL attributes, and isolated reader behavior.

## Acceptance Criteria

- Ingestion, embedding, retrieval, and evaluation metrics are emitted through the OpenTelemetry SDK and OTLP.
- Retrieval latency and candidate count metrics cover exact, BM25, vector, relationship, fusion, reranking, filtering, and total paths.
- PostgreSQL metrics are collected by Alloy's OpenTelemetry Collector PostgreSQL receiver and sent through the shared metrics pipeline.
- The PostgreSQL receiver uses a dedicated least-privilege monitoring role and a database allowlist.
- Query sample and top-query events remain disabled; SQL text, query plans, bind values, and source rows are not exported.
- Metrics tests run without external services, while receiver integration tests run against an isolated local PostgreSQL service.
- Metrics do not expose raw unsanitized chunks, raw queries, SQL, vectors, secrets, PII, citation IDs, or provider payloads.

## Suggested Commit Message

`feat: add opentelemetry retrieval metrics`
