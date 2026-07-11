# 6.2: OpenTelemetry Metrics And Weaviate Monitoring

## Goal

Export bounded application metrics through OTLP and collect Weaviate service metrics through its Prometheus-compatible endpoint.

## Application Metrics

Cover:

- ingestion runs and duration
- objects attempted, written, retried, and failed
- redacted candidates
- Weaviate client latency and errors by bounded operation
- retrieval latency and result count by profile
- MCP availability checks
- evaluation metrics and threshold outcomes
- backup and restore outcomes

## Rules

- no raw queries, source paths, chunk IDs, citation IDs, vectors, credentials, or exception messages as attributes
- application metrics use OpenTelemetry APIs and OTLP
- Weaviate service metrics are scraped by Alloy or Prometheus
- do not add an application scrape endpoint unless a later deployment requires it
- do not configure PostgreSQL metrics

## Checks

- unit tests use an in-memory metric reader
- local integration tests verify application and Weaviate metrics
- cardinality and redaction tests pass
- `mise run ci`

## Acceptance Criteria

Application and Weaviate health are observable with bounded, sanitized metrics.
