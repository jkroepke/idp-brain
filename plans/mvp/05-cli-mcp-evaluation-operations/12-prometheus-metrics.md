# 5.12: Prometheus Metrics

## Goal
Add Prometheus metrics for ingestion, retrieval, evaluation, embedding jobs, redaction, candidate counts, latency, and PostgreSQL observability integration.

## Prerequisites
- Steps 5.1 through 5.11 have added ingest commands, retrieval commands, MCP tools, eval runs, thresholds, and tracing.
- Retrieval events and ingestion runs expose sanitized counters and timings.
- Local runtime includes PostgreSQL and can enable `pg_stat_statements`.
- `ARCHITECTURE.md` remains the source of truth for required metrics and operations tools.

## Files To Create Or Modify
- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/observability/metrics.py`
- `src/idp_brain/ingestion/orchestrator.py`
- `src/idp_brain/retrieval/service.py`
- `src/idp_brain/evaluation/runner.py`
- `src/idp_brain/settings.py`
- `docker-compose.yaml`
- `config/prometheus.yml`
- `tests/observability/test_prometheus_metrics.py`
- `tests/observability/test_metrics_redaction.py`

## Implementation Instructions
1. Add Prometheus client instrumentation with bounded metric labels.
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
7. Use labels such as route, tool, retrieval mode, query profile, source type, index version, redaction status, and outcome only when values are bounded or normalized. Do not use raw queries, source paths, citation IDs, chunk IDs, user-provided text, SQL, exception messages, or high-cardinality identifiers as labels.
8. Expose metrics only through the configured application metrics endpoint or local test registry. Do not expose metrics through MCP tools.
9. Add Prometheus and postgres_exporter configuration to local runtime if not already present. Cover PostgreSQL connection, WAL, replication, lock, index, and query metrics. Use `pg_stat_statements` for PostgreSQL query metrics without logging sensitive query literals.
10. Keep CI deterministic by testing metrics against an isolated in-memory registry without starting Prometheus.

## Tests And Checks
- `uv run pytest tests/observability/test_prometheus_metrics.py tests/observability/test_metrics_redaction.py`
- `docker compose config`
- `mise run ci`
- If local services are available: `mise run up`, run one fixture retrieval and one fixture eval, then confirm metrics scrape output includes the expected metric names.
- Tests must cover metric increments, histograms, PostgreSQL metric target configuration, bounded labels, no raw query labels, no raw chunk labels, no SQL labels, and isolated registry behavior.

## Acceptance Criteria
- Ingestion, embedding, retrieval, and evaluation metrics are emitted with bounded sanitized labels.
- Retrieval latency and candidate count metrics cover exact, BM25, vector, relationship, fusion, reranking, filtering, and total paths.
- Local PostgreSQL observability covers connection, WAL, replication, lock, index, and query metrics through Prometheus/postgres_exporter configuration.
- Prometheus and postgres_exporter can be configured locally without requiring CI to run external services.
- Metrics do not expose raw unsanitized chunks, raw queries, SQL, vectors, secrets, PII, citation IDs as labels, or provider payloads.

## Suggested Commit Message
`feat: add prometheus retrieval metrics`
