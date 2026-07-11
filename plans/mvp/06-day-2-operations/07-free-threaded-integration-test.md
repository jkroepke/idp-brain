# 6.7: Python 3.14 Free-Threaded Integration Test

## Goal

Validate the complete Weaviate and observability stack with uv-managed `cpython-3.14.6+freethreaded` while the GIL remains disabled.

## Dependency Graph

Import and initialize:

- pinned Weaviate Python client and gRPC dependencies
- `opentelemetry-instrumentation-weaviate`
- `opentelemetry-instrumentation-threading`
- `opentelemetry-instrumentation-urllib`
- selected gRPC client instrumentation
- `opentelemetry-instrumentation-logging`
- `opentelemetry-instrumentation-exceptions`
- `pyroscope-otel`
- `pyroscope-io`

## Instructions

1. Install the interpreter through uv; do not compile CPython.
2. Use a dedicated `.venv-freethreaded` synchronized from the lockfile.
3. Assert `Py_GIL_DISABLED == 1` and `sys._is_gil_enabled() is False` before imports, after imports, and after instrumentation initialization.
4. Fail when a dependency lacks a compatible wheel or source build; do not silently omit it.
5. Initialize every instrumentor exactly once and verify idempotency.
6. Run concurrent ingestion, batch writes, direct retrieval, MCP queries, evaluation, `urllib`, gRPC, logging, exception, metrics, traces, and profiling work.
7. Use barriers and bounded queues rather than timing-only sleeps.
8. Verify no deadlocks, crashes, duplicate logical objects, duplicate spans, or lost updates.
9. Verify telemetry contains no credentials, query strings, headers, bodies, messages, vectors, filters, or object content.
10. Create and restore a Weaviate backup after load.
11. Keep the normal Python job; this is an additional CI gate.

## Checks

- exact interpreter and GIL assertions pass
- `mise run test:free-threaded`
- multiple Python threads are visible in profiles
- built-in MCP remains read-only
- Weaviate and application telemetry reach their backends
- backup and restore pass
- `mise run ci`

## Acceptance Criteria

The complete target dependency graph works concurrently under free-threaded Python without silently re-enabling the GIL.
