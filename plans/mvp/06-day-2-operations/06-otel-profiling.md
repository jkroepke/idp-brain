# 6.6: OpenTelemetry Span Profiling

## Goal

Add continuous Python profiling with `pyroscope-otel` so OpenTelemetry traces can be correlated with Pyroscope profiles in Grafana, while profiles are routed through Grafana Alloy and the existing telemetry safety rules remain enforced.

## Prerequisites

- Steps 6.1 through 6.5 are complete.
- Grafana Alloy, Tempo, Pyroscope, and Grafana are healthy in the local Docker Compose stack.
- OpenTelemetry tracing uses one application-owned `TracerProvider` with the contrib instrumentation from Steps 6.3 and 6.4 already registered.
- `ARCHITECTURE.md` remains the source of truth for telemetry safety and bounded attributes.

## Files To Create Or Modify

- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/observability/profiling.py`
- `src/idp_brain/observability/tracing.py`
- `src/idp_brain/observability/instrumentation.py`
- `src/idp_brain/settings.py`
- `docker-compose.yaml`
- `config/observability/alloy.alloy`
- `config/observability/pyroscope.yaml`
- `config/observability/grafana/provisioning/datasources/datasources.yaml`
- `tests/observability/test_profiling.py`
- `tests/observability/test_profiling_redaction.py`
- `tests/integration/test_profile_trace_correlation.py`

## Implementation Instructions

1. Add and lock `pyroscope-otel` from `https://github.com/grafana/otel-profiling-python` and its `pyroscope-io` dependency through the normal `uv` workflow. Do not install an unpinned Git checkout in the default environment.
2. Configure the Pyroscope Python profiler before any OpenTelemetry spans are created. Keep profiling disabled by default in unit tests and configurable through application settings.
3. Configure the profiler with:
   - application name `idp-brain`.
   - a configurable server address that points to Grafana Alloy's Pyroscope-compatible HTTP receiver in the local stack.
   - a bounded and configurable sample rate.
   - `gil_only=False` so profiling also works when the Python 3.14 free-threaded runtime is tested in Step 6.7.
   - only reviewed low-cardinality static tags such as deployment environment and service version.
4. Register `pyroscope.otel.PyroscopeSpanProcessor` on the existing OpenTelemetry `TracerProvider`. Do not create a second provider and do not replace the existing OTLP trace exporter or any contrib instrumentation.
5. Preserve initialization order:
   - configure Pyroscope.
   - create or obtain the application `TracerProvider`.
   - register `PyroscopeSpanProcessor`.
   - register the existing OTLP span processor and exporter.
   - initialize SQLAlchemy, psycopg2, threading, urllib3, logging, and exception instrumentation against the same provider and context pipeline.
   - set the provider once.
6. Use bounded root span names. Do not place raw queries, source paths, citation IDs, chunk IDs, user-provided text, SQL, URL query strings, headers, request bodies, secrets, PII, or provider payloads in span names, profile labels, profiler tags, or profile metadata.
7. Verify that root spans contain the `pyroscope.profile.id` attribute and that the profiler adds the expected trace and span correlation tags without changing child-span behavior produced by manual or contrib instrumentation.
8. Configure Grafana Alloy with `pyroscope.receive_http` and forward profiles through `pyroscope.write` to the local Pyroscope backend. Keep the receiver bound to localhost at the host boundary.
9. Provision a Pyroscope Grafana data source and configure trace-to-profile navigation from Tempo. A selected trace must open the matching profile using the correlation data produced by `PyroscopeSpanProcessor`.
10. Verify database and outbound HTTP spans created by contrib instrumentation retain trace-to-profile correlation without adding SQL text, parameters, URL query strings, headers, or bodies to profile labels.
11. Verify context propagated by `ThreadingInstrumentor` keeps thread and thread-pool work attached to the correct root trace and profile without introducing high-cardinality thread names or identifiers as profile tags.
12. Add graceful shutdown that flushes OpenTelemetry spans and stops profiling without hanging CLI, MCP, evaluation, or worker processes.
13. Treat the native `pyroscope-io` extension as part of the Step 6.7 free-threaded compatibility gate. If importing or running it re-enables the global interpreter lock, crashes, or lacks a compatible build, report that as a blocker rather than weakening the gate.

## Tests And Checks

- `uv run pytest tests/observability/test_profiling.py tests/observability/test_profiling_redaction.py`
- `docker compose config`
- Start the complete stack and run a deterministic operation long enough to produce statistically useful profile samples.
- Verify a profile is queryable in Pyroscope for `idp-brain`.
- Verify the corresponding root span contains `pyroscope.profile.id` and Grafana can navigate from the Tempo trace to the matching profile.
- Verify SQLAlchemy, direct psycopg2, urllib3, and threaded fixture spans remain correlated with the same root profile.
- Verify profiling-disabled mode produces no profiler traffic and does not alter tracing or contrib instrumentation behavior.
- Verify raw fixture queries, secrets, PII, paths, SQL, URL query strings, headers, request bodies, chunk content, and provider payloads do not appear in profile labels or metadata.
- `mise run ci`

## Acceptance Criteria

- Python continuous profiles are received by Grafana Alloy and stored in Pyroscope.
- `PyroscopeSpanProcessor` links root OpenTelemetry spans with their profiles without replacing the existing OTLP trace pipeline or contrib instrumentation.
- Database, HTTP, and threaded child work remains correlated with the correct root profile.
- Grafana has a provisioned Pyroscope data source and working trace-to-profile navigation.
- Profile labels and tags are bounded, low-cardinality, and sanitized.
- Profiling can be disabled for tests and local workflows that do not need it.
- The profiling dependencies are included in the Python 3.14 free-threaded compatibility and concurrency test.

## Suggested Commit Message

`feat: add opentelemetry span profiling`
