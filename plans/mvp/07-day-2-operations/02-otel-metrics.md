# 7.2: OpenTelemetry Metrics And Weaviate Monitoring

## Goal

Add OpenTelemetry application metrics for ingestion, Weaviate writes, retrieval, evaluation, redaction, candidate counts, and latency, and combine them with Weaviate's Prometheus-compatible service metrics.

## Prerequisites

- Step 7.1 provides the local metrics pipeline.
- Phase 6 provides Weaviate ingestion and retrieval adapters.
- Retrieval and ingestion events expose sanitized counters and timings.

## Files To Create Or Modify

- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/observability/metrics.py`
- ingestion, retrieval, evaluation, and store adapters
- `src/idp_brain/settings.py`
- Alloy metrics configuration
- metrics and integration tests

## Implementation Instructions

1. Configure the OpenTelemetry SDK `MeterProvider`, periodic reader, and OTLP exporter. Unit tests use an in-memory reader.
2. Define ingestion metrics for runs, changed objects, failed objects, redacted chunks, tombstones, and batch retries.
3. Define Weaviate client metrics for bounded operation types such as bootstrap, batch write, object fetch, filter query, hybrid query, backup, and restore.
4. Define retrieval latency for exact lookup, hybrid search, structured lookup, policy filtering, reranking, evidence packaging, and total duration.
5. Define candidate-count metrics before and after reranking and evidence packaging.
6. Define evaluation metrics for Recall@k, MRR, nDCG@10, hit rate, context precision, context recall, abstention correctness, and gate results.
7. Use only bounded attributes such as operation, query profile, target vector, content kind, outcome, collection generation, and error class.
8. Never use raw queries, object IDs, source paths, citations, chunks, filters, vectors, provider payloads, or exception messages as metric attributes.
9. Export application metrics through OTLP only. Do not add an application scrape endpoint.
10. Scrape Weaviate's metrics endpoint with Alloy and retain the service, shard, collection, indexing, request, resource, backup, and replication metric families that exist in the pinned version and are useful to the deployment.
11. Add recording rules or dashboards for:
    - Weaviate availability and request failures.
    - batch import throughput and failures.
    - vector index activity and resource pressure.
    - object counts and shard health.
    - backup and restore outcomes.
12. Drop metric families or labels that expose unbounded collection, tenant, path, or request values when they are not required.
13. Keep tests independent from exact upstream metric names where the pinned version may change them; integration tests validate an explicit allowlist for the pinned release.

## Tests And Checks

- Run unit tests for counters, histograms, bounded attributes, and redaction.
- Start the local stack and run fixture ingestion, retrieval, and evaluation.
- Verify application metrics arrive through OTLP.
- Verify expected Weaviate metric families arrive through scraping.
- Verify no source content, query text, vectors, API keys, or provider payloads appear in labels.
- `mise run ci`

## Acceptance Criteria

- Application and Weaviate service metrics are visible in one Prometheus backend.
- Retrieval metrics describe the Weaviate path, not deleted SQL stages.
- Metrics have bounded, reviewed attributes.
- Unit tests run without external services; integration tests use isolated Weaviate.
- No PostgreSQL metrics component remains.

## Suggested Commit Message

`feat: add weaviate opentelemetry metrics`
