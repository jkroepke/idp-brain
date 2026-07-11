# 6.1: Observability Backend Stack

## Goal

Run a pinned local observability stack with Grafana Alloy as the application-facing gateway, Prometheus for metrics, Tempo for traces, Loki for logs, Pyroscope for profiles, and Grafana for exploration.

## Instructions

- receive application metrics, logs, and traces through OTLP
- receive Python profiles through Alloy's Pyroscope-compatible endpoint
- scrape Weaviate's Prometheus-compatible metrics
- provision Grafana data sources and cross-signal correlations
- keep receiver ports localhost-bound in local development
- use bounded queues, retries, memory protection, health checks, and persistent local volumes
- do not add a PostgreSQL receiver or `postgres_exporter`

## Checks

- `docker compose config`
- all services become healthy
- synthetic signals reach each backend
- Weaviate metrics are queryable
- Grafana data sources are provisioned
- `mise run ci`

## Acceptance Criteria

The complete local stack starts reproducibly and observes Weaviate plus the application without restoring any PostgreSQL-specific component.
