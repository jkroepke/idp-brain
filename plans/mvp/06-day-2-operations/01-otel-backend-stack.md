# 6.1: OpenTelemetry Backend Stack

## Goal

Add a complete local observability backend stack to `docker-compose.yaml` with Grafana Alloy as the application-facing telemetry gateway, Prometheus for metrics, Tempo for traces, Loki for logs, Pyroscope for profiles, and Grafana with preconfigured data sources.

## Prerequisites

- Phase 5 is complete and the local PostgreSQL service is healthy.
- Docker Compose is the documented local runtime interface.
- The stack is for local development and integration testing, not production high availability.
- `ARCHITECTURE.md` remains the source of truth for telemetry safety and data handling.

## Files To Create Or Modify

- `docker-compose.yaml`
- `mise.toml`
- `config/observability/alloy.alloy`
- `config/observability/prometheus.yaml`
- `config/observability/tempo.yaml`
- `config/observability/loki.yaml`
- `config/observability/pyroscope.yaml`
- `config/observability/grafana/provisioning/datasources/datasources.yaml`
- Optional: `config/observability/grafana/provisioning/dashboards/`
- Optional: `.env.example` for documented local overrides only

## Implementation Instructions

1. Add pinned container images for Grafana Alloy, Prometheus, Tempo, Loki, Pyroscope, and Grafana. Do not use floating `latest` tags.
2. Configure Grafana Alloy as the only application-facing telemetry gateway:
   - OTLP/gRPC on port `4317`.
   - OTLP/HTTP on port `4318`.
   - receive metrics, logs, and traces through `otelcol.receiver.otlp`.
   - receive Python profiles through a Pyroscope-compatible `pyroscope.receive_http` endpoint.
   - add bounded batching, memory protection, retries, and sending queues where supported.
3. Route metrics from Alloy to the Prometheus OTLP/HTTP receiver. Enable the receiver with `--web.enable-otlp-receiver`, use the `/api/v1/otlp` base endpoint, allow a bounded out-of-order window, and promote only reviewed low-cardinality resource attributes.
4. Route traces from Alloy to Tempo through OTLP. Use Tempo monolithic mode and local storage for the development stack.
5. Route logs from Alloy to Loki through its native OTLP/HTTP endpoint. Keep structured metadata enabled and configure only a small reviewed set of resource attributes as index labels.
6. Route profiles from Alloy to Pyroscope through `pyroscope.write`. Use Pyroscope monolithic mode and persistent local storage for development. Profiles use the Pyroscope ingest protocol because the Python profiling SDK does not emit profiles as an OTLP signal.
7. Provision Grafana data sources from files so a fresh `docker compose up` includes working metrics, logs, traces, and profiles data sources without UI setup.
8. Configure Grafana correlations where supported:
   - traces to logs by `trace_id`, `service.name`, and a bounded time window.
   - traces to metrics by `service.name` and reviewed resource attributes.
   - logs to traces through the OpenTelemetry trace identifier fields.
   - traces to profiles through the correlation attributes and tags emitted by `pyroscope-otel`.
9. Add named volumes for backend state and health checks for all services. Application startup must not depend on Grafana being healthy, but integration tests may wait for every backend.
10. Keep all backend ports bound to localhost by default. Do not configure authentication-free receivers on non-loopback host interfaces for the local profile.
11. Add `mise` tasks for starting, stopping, and checking the complete stack while preserving the existing database-only workflow.

## Tests And Checks

- `docker compose config`
- `mise run up`
- Wait for PostgreSQL, Alloy, Prometheus, Tempo, Loki, Pyroscope, and Grafana health checks.
- Send synthetic OTLP metrics, logs, and traces to Alloy and verify that every signal reaches its configured backend.
- Send a synthetic profile through Alloy's Pyroscope-compatible receiver and verify it reaches Pyroscope.
- Query Grafana's data source health API or the individual backend APIs to confirm all provisioned data sources are usable.
- `mise run ci`

## Acceptance Criteria

- One Docker Compose command starts PostgreSQL and the complete local observability stack.
- Applications send metrics, logs, and traces to Grafana Alloy through OTLP and profiles through Alloy's Pyroscope-compatible HTTP receiver.
- Metrics, logs, traces, and profiles are queryable from their backends.
- Grafana starts with working, preconfigured data sources and cross-signal correlations.
- The stack uses pinned images, persistent local volumes, health checks, and localhost-only receiver bindings by default.
- No raw unsanitized chunks, raw queries, secrets, PII, vectors, SQL parameters, or provider payloads are introduced through backend configuration.

## Suggested Commit Message

`ops: add local observability backend stack`
