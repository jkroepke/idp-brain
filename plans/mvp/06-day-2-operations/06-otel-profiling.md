# 6.6: OpenTelemetry Span Profiling

## Goal

Add continuous Python profiling with `pyroscope-otel` and correlate root traces with Pyroscope profiles through Grafana.

## Instructions

- pin `pyroscope-otel` and `pyroscope-io`
- configure profiling before application spans are created
- use the existing application `TracerProvider`
- register `PyroscopeSpanProcessor`
- route profiles through Alloy to Pyroscope
- set `gil_only=False`
- use only reviewed low-cardinality static tags
- keep raw queries, paths, chunk IDs, object content, vectors, credentials, and provider payloads out of labels
- provision trace-to-profile navigation in Grafana
- make profiling optional and shutdown bounded

## Checks

- profiles are queryable
- root spans contain correlation data
- Weaviate client and threaded child work correlate with the root profile
- disabled mode creates no profiler traffic
- `mise run ci`

## Acceptance Criteria

Profiles correlate with traces without adding high-cardinality or sensitive labels.
