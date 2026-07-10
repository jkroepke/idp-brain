# 6.2: OpenTelemetry Metrics

## Goal
Add OpenTelemetry metrics for ingestion, retrieval, evaluation, embedding jobs, redaction, candidate counts, latency, and PostgreSQL operations, exported through OTLP to the backend stack from Step 6.1.

## Prerequisites
- Step 6.1 has added the local OTLP gateway and metrics backend.
- Steps 5.1 through 5.10 and 5.13 have added ingest commands, retrieval commands, MCP tools, eval runs, thresholds, and CI evaluation.
- Retrieval events and ingestion runs expose sanitized counters and timings.
- Local runtime includes PostgreSQL and can enable `pg_stat_statements`.
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
- `tests/observability/test_otel_metrics.py`
- `tests/observability/test_metrics_redaction.py`

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
8. Export metrics through OTLP only. Do not add an application scrape endpoint and do not expose metrics through MCP tools.
9. Configure PostgreSQL telemetry through the OpenTelemetry PostgreSQL receiver in the local gateway or an equivalent collector-native receiver. Cover connection, WAL, replication, lock, index, and query metrics. Use `pg_stat_statements` without recording sensitive query literals.
10. Propagate the same service resource attributes and correlation identifiers used by logs and traces.
11. Keep CI deterministic by testing instruments against an isolated in-memory reader without starting external services.

## Tests And Checks
- `uv run pytest tests/observability/test_otel_metrics.py tests/observability/test_metrics_redaction.py`
- `docker compose config`
- `mise run ci`
- If local services are available: `mise run up`, run one fixture ingestion, retrieval, and eval, then query the metrics backend through Grafana and confirm the expected instrument names exist.
- Tests must cover counter increments, histogram recordings, PostgreSQL receiver configuration, bounded attributes, no raw query attributes, no raw chunk attributes, no SQL attributes, and isolated reader behavior.

## Acceptance Criteria
- Ingestion, embedding, retrieval, evaluation, and PostgreSQL metrics are emitted through the OpenTelemetry SDK and OTLP.
- Retrieval latency and candidate count metrics cover exact, BM25, vector, relationship, fusion, reranking, filtering, and total paths.
- PostgreSQL telemetry covers connection, WAL, replication, lock, index, and query behavior.
- Metrics tests run without external services.
- Metrics do not expose raw unsanitized chunks, raw queries, SQL, vectors, secrets, PII, citation IDs, or provider payloads.

## Suggested Commit Message
`feat: add opentelemetry retrieval metrics`
