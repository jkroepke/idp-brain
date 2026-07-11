# 7.6: OpenTelemetry Span Profiling

## Goal

Add continuous Python profiling with `pyroscope-otel` so OpenTelemetry traces can be correlated with Pyroscope profiles in Grafana while profiles are routed through Grafana Alloy.

## Prerequisites

- Steps 7.1 through 7.5 are complete.
- Grafana Alloy, Tempo, Pyroscope, and Grafana are healthy.
- Tracing uses one application-owned `TracerProvider`.

## Files To Create Or Modify

- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/observability/profiling.py`
- tracing and instrumentation modules
- settings
- Docker Compose and Alloy configuration
- Grafana data source provisioning
- profiling and correlation tests

## Implementation Instructions

1. Add and lock `pyroscope-otel` and `pyroscope-io` through the normal `uv` workflow.
2. Configure the profiler before spans are created. Keep profiling disabled by default in unit tests.
3. Configure:
   - application name `idp-brain`.
   - Alloy's Pyroscope-compatible receiver address.
   - bounded sample rate.
   - `gil_only=False` for Step 7.7.
   - reviewed low-cardinality static tags only.
4. Register `PyroscopeSpanProcessor` on the existing `TracerProvider`. Do not create a second provider.
5. Preserve initialization order: profiler, tracer provider, Pyroscope processor, OTLP processor, contrib instrumentation, provider registration.
6. Initialize gRPC, HTTP, threading, logging, and exception instrumentation against the same context pipeline.
7. Keep raw queries, source paths, object IDs, chunks, vectors, filters, provider payloads, secrets, PII, headers, and bodies out of span names and profile tags.
8. Verify root spans contain the expected profile correlation attribute.
9. Route profiles through Alloy to Pyroscope.
10. Provision Pyroscope in Grafana and configure trace-to-profile navigation.
11. Verify Weaviate HTTP/gRPC child spans remain correlated without leaking payloads.
12. Verify threaded work remains attached to the correct root profile without high-cardinality thread tags.
13. Flush spans and stop profiling with bounded shutdown.
14. Treat `pyroscope-io` compatibility as part of the free-threaded gate.

## Tests And Checks

- Run profiling and redaction unit tests.
- Produce a deterministic profile in the local stack.
- Verify the matching root span and trace-to-profile navigation.
- Verify Weaviate, HTTP, gRPC, and threaded child spans share the root correlation.
- Verify disabled profiling changes no trace behavior.
- Verify no unsafe dynamic label appears.
- `mise run ci`

## Acceptance Criteria

- Profiles reach Pyroscope through Alloy.
- Root spans link to matching profiles.
- Weaviate and threaded work remain correlated.
- Profile labels are bounded and sanitized.
- Profiling can be disabled.
- Dependencies are covered by the free-threaded compatibility test.

## Suggested Commit Message

`feat: add opentelemetry span profiling`
