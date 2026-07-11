# 7.7: Python 3.14 Free-Threaded Integration Test

## Goal

Validate the complete local Weaviate and observability setup with the uv-managed CPython 3.14.6 free-threaded interpreter running with the global interpreter lock disabled.

## Prerequisites

- Steps 7.1 through 7.6 are complete.
- The complete Docker Compose stack is healthy.
- Deterministic sanitized ingestion, retrieval, MCP, evaluation, HTTP, gRPC, exception, threading, profiling, backup, and restore fixtures exist.
- The pinned uv version exposes `cpython-3.14.6+freethreaded`.

## Files To Create Or Modify

- `docker-compose.yaml`
- `mise.toml`
- free-threaded CI workflow or job
- free-threaded runtime and concurrent workload tests
- Weaviate and telemetry integration tests
- dependency configuration for the free-threaded environment

## Implementation Instructions

1. Install `cpython-3.14.6+freethreaded` through uv. Do not compile CPython or maintain a custom Python image.
2. Create a dedicated `.venv-freethreaded` from the committed lockfile.
3. Before imports, verify:
   - `Py_GIL_DISABLED == 1`.
   - `sys._is_gil_enabled() is False`.
   - the exact uv-managed interpreter is selected.
4. Import the complete dependency graph, including:
   - Weaviate Python client and gRPC dependencies.
   - `pyroscope-otel` and `pyroscope-io`.
   - OpenTelemetry threading, HTTP, gRPC, logging, and exception instrumentation.
5. Repeat the GIL assertion after imports and fail if any extension re-enables it.
6. Record missing compatible wheels or source builds as blockers.
7. Configure profiling with `gil_only=False` and verify samples from multiple active Python threads.
8. Initialize all contrib instrumentors once and verify idempotency.
9. Add `mise run test:free-threaded` that starts the complete stack, bootstraps Weaviate, ingests fixtures, runs concurrent work, validates telemetry, creates a backup, restores it, and tears down resources after failure.
10. Implement a deterministic multithreaded workload that concurrently exercises:
    - ingestion and incremental updates.
    - exact, lexical, vector, hybrid, and structured retrieval.
    - MCP tools.
    - evaluation.
    - Weaviate batch writes and object fetches.
    - local HTTP and gRPC fixture calls.
    - uncaught thread and asyncio exception fixtures.
    - metrics, logs, traces, and continuous profiling.
11. Use barriers and bounded queues instead of timing-only sleeps.
12. Verify correctness:
    - no crashes, deadlocks, lost updates, or duplicate logical objects.
    - deterministic IDs and active-generation rules remain correct.
    - corpus eligibility, redaction, citations, and memory expiry remain correct.
    - trace context propagates to threads and transport spans.
    - HTTP/gRPC spans contain no credentials, bodies, messages, vectors, or object content.
    - exceptions produce one sanitized record per output path.
13. Verify Weaviate metrics, application telemetry, Grafana data sources, and trace-to-profile navigation under concurrent load.
14. Create and restore a Weaviate backup after concurrent load.
15. Run the job on a runner with at least two CPU cores while retaining the normal Python job.

## Tests And Checks

- Install and resolve the uv-managed free-threaded interpreter.
- Verify version and GIL state before and after imports.
- `mise run test:free-threaded`
- Repeat the bounded concurrent workload.
- Query metrics, logs, traces, profiles, and Weaviate service health.
- Verify backup and restore after load.
- `mise run ci`

## Acceptance Criteria

- The exact uv-managed free-threaded interpreter is used and the GIL remains disabled.
- No dependency silently re-enables the GIL.
- Multiple threads exercise the full Weaviate pipeline without correctness failures or deadlocks.
- Transport and application telemetry are sanitized and correctly correlated.
- Weaviate metrics and application signals reach their backends.
- A backup created after load restores successfully.
- The free-threaded job is an additional CI gate, not a replacement for normal tests.

## Suggested Commit Message

`test: validate uv-managed free-threaded python`
