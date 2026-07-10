# 6.7: Python 3.14 Free-Threaded Integration Test

## Goal

Validate the complete local setup with the uv-managed CPython 3.14.6 free-threaded interpreter running with the global interpreter lock disabled, including concurrent application work, OpenTelemetry contrib instrumentation, PostgreSQL receiver metrics, continuous profiles, and database backup and restore.

## Prerequisites

- Steps 6.1 through 6.6 are complete.
- The complete Docker Compose stack, including Pyroscope and the PostgreSQL receiver, is healthy.
- Sanitized deterministic ingestion, retrieval, MCP, evaluation, database, HTTP, exception, and threading fixtures are available.
- The test environment has enough CPU and memory to run the stack and multiple Python worker threads.
- The pinned uv version exposes `cpython-3.14.6+freethreaded` in `uv python list`.

## Files To Create Or Modify

- `docker-compose.yaml`
- `mise.toml`
- `.github/workflows/free-threaded.yaml` or an isolated job in `.github/workflows/ci.yaml`
- `tests/free_threaded/verify_runtime.py`
- `tests/free_threaded/test_concurrent_workload.py`
- `tests/free_threaded/test_contrib_instrumentation.py`
- `tests/integration/test_otel_stack.py`
- `tests/integration/test_postgresql_receiver.py`
- `tests/integration/test_profile_trace_correlation.py`
- `tests/integration/test_backup_restore.py`
- Dependency configuration required for the Python 3.14 free-threaded environment

## Implementation Instructions

1. Install the exact uv-managed free-threaded interpreter with `uv python install cpython-3.14.6+freethreaded`. Do not compile CPython from source and do not add a dedicated Python build Dockerfile.
2. Resolve the interpreter with `uv python find cpython-3.14.6+freethreaded` and create a dedicated project environment, for example by setting `UV_PROJECT_ENVIRONMENT=.venv-freethreaded` and running `uv sync --python cpython-3.14.6+freethreaded --locked`. Do not replace the normal Python 3.14 environment.
3. Before importing application dependencies, verify:
   - `sysconfig.get_config_var("Py_GIL_DISABLED") == 1`.
   - `sys._is_gil_enabled() is False`.
   - `python -VV` identifies CPython 3.14.6 free-threaded.
   - the resolved executable belongs to uv's managed Python installation and not a system interpreter selected accidentally.
4. Import the complete application dependency graph, including:
   - `pyroscope-otel` and `pyroscope-io`.
   - `opentelemetry-instrumentation-sqlalchemy`.
   - `opentelemetry-instrumentation-threading`.
   - `opentelemetry-instrumentation-urllib3`.
   - `opentelemetry-instrumentation-psycopg2`.
   - `opentelemetry-instrumentation-logging`.
   - `opentelemetry-instrumentation-exceptions`.
5. After all imports, repeat `sys._is_gil_enabled()`. Fail immediately if any extension module re-enables the lock. Do not downgrade this condition to a warning or skip.
6. Install and lock dependencies for the free-threaded ABI. Record packages that do not provide compatible wheels or successful source builds as explicit blockers.
7. Configure profiling with `gil_only=False`. Verify the profiler starts, samples multiple active Python threads, and shuts down cleanly under the free-threaded runtime.
8. Initialize all OpenTelemetry contrib instrumentors exactly once and verify repeated setup is idempotent:
   - `LoggingInstrumentor` injects trace context without taking over the application's standard-output format.
   - `UnhandledExceptionInstrumentor` observes uncaught process, thread, and asyncio task failures.
   - `ThreadingInstrumentor` propagates context across `Thread`, `Timer`, and `ThreadPoolExecutor` workers.
   - `SQLAlchemyInstrumentor` instruments application-owned engines.
   - `Psycopg2Instrumentor` instruments only direct psycopg2 connections not already covered by SQLAlchemy.
   - `URLLib3Instrumentor` strips URL query parameters and excludes telemetry endpoints.
9. Add a `mise run test:free-threaded` task that:
   - installs or verifies `cpython-3.14.6+freethreaded` through uv.
   - synchronizes the dedicated `.venv-freethreaded` environment from the committed lockfile.
   - asserts the exact interpreter identity and disabled-GIL state before running tests.
   - starts the complete Docker Compose stack.
   - applies migrations and seeds sanitized fixtures.
   - runs the concurrent workload.
   - runs the database backup and restore smoke test.
   - queries every telemetry backend, the PostgreSQL receiver output, and Grafana data source health.
   - tears down test resources even after failure.
10. Implement a deterministic multithreaded workload with `threading` and `concurrent.futures.ThreadPoolExecutor` that concurrently exercises:
   - fixture ingestion and incremental updates.
   - exact, BM25, vector, and fused retrieval.
   - read-only MCP `search`, `fetch`, `explain_search`, and `list_sources` calls.
   - evaluation runs.
   - SQLAlchemy-managed database operations.
   - a bounded direct psycopg2 fixture path that is not wrapped by SQLAlchemy.
   - outbound urllib3 requests to a local fixture server.
   - uncaught worker-thread and asyncio task exception fixtures in isolated subprocesses.
   - metrics, logs, and traces emitted through OTLP.
   - continuous profiling with trace-to-profile correlation.
11. Use barriers and bounded work queues so tests create real overlapping work without depending on timing-only sleeps. Protect application-owned shared mutable state with explicit synchronization primitives.
12. Verify correctness under concurrency:
   - no crashes, deadlocks, data races visible through incorrect results, duplicate final writes, or lost updates.
   - corpus eligibility, redaction, citation, index-version, and transaction boundaries remain correct.
   - every completed operation has expected telemetry and correlation identifiers.
   - active trace context propagates into thread and thread-pool work.
   - SQLAlchemy and psycopg2 instrumentation never create duplicate spans for the same database operation.
   - urllib3 spans contain no query strings, headers, bodies, credentials, or telemetry-recursion spans.
   - uncaught exceptions produce one sanitized local record and one OpenTelemetry log record.
   - profile samples include work from multiple worker threads and do not contain unsafe dynamic labels.
13. Verify the PostgreSQL receiver under concurrent load:
   - it authenticates with the dedicated least-privilege monitoring role.
   - expected database metrics reach the shared metrics backend.
   - query sample and top-query events remain disabled.
   - no SQL text, query plans, bind values, or source rows appear in telemetry.
14. Verify the whole operations path after concurrent load:
   - metrics, logs, traces, and profiles are queryable from their backends.
   - Grafana data sources remain healthy.
   - a Tempo trace can navigate to its matching Pyroscope profile.
   - database spans correlate with application traces without exposing SQL text or parameters.
   - a database archive created after the workload restores successfully.
15. Run the test in GitHub Actions on a runner with at least two CPU cores. Install the same pinned uv version, install `cpython-3.14.6+freethreaded` through uv, cache uv's managed Python and package directories where practical, and keep external model providers disabled.
16. Keep the normal Python 3.14 test job. The free-threaded job is an additional compatibility and concurrency gate, not a replacement.

## Tests And Checks

- `uv python install cpython-3.14.6+freethreaded`
- `uv python find cpython-3.14.6+freethreaded`
- Run the managed interpreter with `python -VV` and verify the exact version and free-threaded variant.
- Run startup assertions for `Py_GIL_DISABLED` and `sys._is_gil_enabled()` before and after all application, profiling, database-driver, and OpenTelemetry contrib imports.
- `mise run test:free-threaded`
- Repeat the concurrent workload enough times to expose ordering defects while keeping the runtime bounded.
- Verify context propagation through `Thread`, `Timer`, and `ThreadPoolExecutor`.
- Verify SQLAlchemy and direct psycopg2 instrumentation create sanitized, non-duplicated spans.
- Verify urllib3 instrumentation strips query parameters and excludes the local telemetry endpoints.
- Verify uncaught process, thread, and asyncio task exceptions are captured without duplicate or unsafe records.
- Query PostgreSQL receiver metrics and verify query sample and top-query events remain disabled.
- Query metrics, logs, traces, and profiles for the test service instance and verify cross-signal correlation.
- Verify `pyroscope.profile.id` appears on root spans and trace-to-profile navigation resolves the corresponding profile.
- Run the backup and restore smoke test after concurrent load.
- `mise run ci`

## Acceptance Criteria

- The integration test uses the uv-managed `cpython-3.14.6+freethreaded` interpreter and confirms the lock is disabled before and after importing all application, profiling, database-driver, and contrib instrumentation dependencies.
- The test does not compile CPython or maintain a custom free-threaded Python image.
- No dependency, including `pyroscope-io`, psycopg2, or the OpenTelemetry contrib packages, silently re-enables the lock.
- Multiple Python threads concurrently exercise ingestion, retrieval, MCP, evaluation, database access, outbound HTTP, exception handling, telemetry, and profiling without correctness failures, crashes, or deadlocks.
- Thread context propagates correctly, database spans are not duplicated, outbound HTTP spans are sanitized, and uncaught exceptions are captured once per output path.
- PostgreSQL metrics reach the shared backend through Alloy's collector-native receiver without exporting SQL text or query plans.
- Metrics, logs, and traces reach their configured backends through OTLP; profiles reach Pyroscope through Grafana Alloy.
- Root traces correlate with profiles in Grafana.
- A backup created after the concurrent workload restores successfully.
- The free-threaded integration test runs as an explicit local task and a CI gate while the normal interpreter test remains available.

## Suggested Commit Message

`test: validate uv-managed free-threaded python`
