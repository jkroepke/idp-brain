# 7.1: OpenTelemetry Backend Stack

## Goal

Add a complete local observability backend stack with Grafana Alloy as the application-facing telemetry gateway, Prometheus for metrics, Tempo for traces, Loki for logs, Pyroscope for profiles, and Grafana with preconfigured data sources. Include scraping of Weaviate's Prometheus-compatible metrics.

## Prerequisites

- Phase 6 is complete and Weaviate is the only persistent store.
- Docker Compose is the documented local runtime interface.
- The stack is for local development and integration testing, not production high availability.
- `ARCHITECTURE.md` remains the source of truth for telemetry safety.

## Files To Create Or Modify

- `docker-compose.yaml`
- `mise.toml`
- `config/observability/alloy.alloy`
- `config/observability/prometheus.yaml`
- `config/observability/tempo.yaml`
- `config/observability/loki.yaml`
- `config/observability/pyroscope.yaml`
- Grafana provisioning files
- optional local dashboards

## Implementation Instructions

1. Add pinned images for Grafana Alloy, Prometheus, Tempo, Loki, Pyroscope, and Grafana. Do not use floating tags.
2. Configure Grafana Alloy as the application telemetry gateway:
   - OTLP/gRPC on port `4317`.
   - OTLP/HTTP on port `4318`.
   - bounded batching, memory protection, retries, and queues.
   - Pyroscope-compatible HTTP receiver for Python profiles.
3. Route application metrics from Alloy to Prometheus through one documented supported pipeline.
4. Scrape the pinned Weaviate metrics endpoint with Alloy. Forward those metrics to Prometheus through the same metrics destination.
5. Restrict Weaviate metric labels to the labels emitted by the pinned version and drop or rewrite unbounded labels when required.
6. Route traces from Alloy to Tempo through OTLP.
7. Route logs from Alloy to Loki through OTLP/HTTP.
8. Route profiles from Alloy to Pyroscope through `pyroscope.write`.
9. Provision Grafana data sources from files so a fresh stack has working metrics, logs, traces, and profiles without UI setup.
10. Configure correlations where supported:
    - traces to logs.
    - traces to metrics.
    - logs to traces.
    - traces to profiles.
11. Add volumes and health checks for every backend.
12. Bind backend and receiver ports to localhost by default.
13. Add `mise` tasks for starting, stopping, and checking the complete stack while preserving a Weaviate-only runtime task.
14. Do not introduce `postgres_exporter`, an OpenTelemetry PostgreSQL receiver, SQL dashboards, or database credentials.

## Tests And Checks

- `docker compose config`
- `mise run up`
- Wait for Weaviate, Alloy, Prometheus, Tempo, Loki, Pyroscope, and Grafana health checks.
- Send synthetic OTLP metrics, logs, and traces through Alloy.
- Send a synthetic profile through Alloy.
- Verify Weaviate metrics reach Prometheus.
- Verify Grafana data sources are healthy.
- `mise run ci`

## Acceptance Criteria

- One Docker Compose command starts Weaviate and the complete local observability stack.
- Application metrics, logs, and traces flow through Alloy.
- Weaviate metrics are available in Prometheus.
- Profiles are available in Pyroscope.
- Grafana starts with provisioned data sources and correlations.
- No source content, raw queries, vectors, provider payloads, secrets, or credentials enter backend configuration.

## Suggested Commit Message

`ops: add local observability backend stack`
