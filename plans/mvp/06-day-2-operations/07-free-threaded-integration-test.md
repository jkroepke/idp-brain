# 6.7: Python 3.14 Free-Threaded Integration Test

## Goal

Validate the complete local setup with a CPython 3.14 free-threaded build running with the global interpreter lock disabled, including concurrent application work, metrics, logs, traces, continuous profiles, and database backup and restore.

## Prerequisites

- Steps 6.1 through 6.6 are complete.
- The complete Docker Compose stack, including Pyroscope, is healthy.
- Sanitized deterministic ingestion, retrieval, MCP, and evaluation fixtures are available.
- The test environment has enough CPU and memory to run the stack and multiple Python worker threads.

## Files To Create Or Modify

- `docker-compose.yaml`
- `mise.toml`
- `Dockerfile.free-threaded`
- `.github/workflows/free-threaded.yaml` or an isolated job in `.github/workflows/ci.yaml`
- `tests/free_threaded/verify_runtime.py`
- `tests/free_threaded/test_concurrent_workload.py`
- `tests/integration/test_otel_stack.py`
- `tests/integration/test_profile_trace_correlation.py`
- `tests/integration/test_backup_restore.py`
- Dependency configuration required for the Python 3.14 free-threaded environment

## Implementation Instructions

1. Build CPython 3.14 from an official source release with `--disable-gil`, or use a pinned, verified CPython 3.14 free-threaded image that provides the same build configuration. Do not fall back to the normal interpreter.
2. Before importing application dependencies, verify:
   - `sysconfig.get_config_var("Py_GIL_DISABLED") == 1`.
   - `sys._is_gil_enabled() is False`.
   - `python -VV` identifies a free-threaded build.
3. Import the complete application dependency graph, including `pyroscope-otel` and `pyroscope-io`, then repeat `sys._is_gil_enabled()`. Fail immediately if any extension module re-enables the lock. Do not downgrade this condition to a warning or skip.
4. Install and lock dependencies for the free-threaded ABI. Record packages that do not provide compatible wheels or source builds as explicit blockers.
5. Configure profiling with `gil_only=False`. Verify the profiler starts, samples multiple active Python threads, and shuts down cleanly under the free-threaded runtime.
6. Add a `mise run test:free-threaded` task that:
   - builds the free-threaded runtime.
   - starts the complete Docker Compose stack.
   - applies migrations and seeds sanitized fixtures.
   - runs the concurrent workload.
   - runs the database backup and restore smoke test.
   - queries every telemetry backend and Grafana data source health.
   - tears down test resources even after failure.
7. Implement a deterministic multithreaded workload with `threading` or `concurrent.futures.ThreadPoolExecutor` that concurrently exercises:
   - fixture ingestion and incremental updates.
   - exact, BM25, vector, and fused retrieval.
   - read-only MCP `search`, `fetch`, `explain_search`, and `list_sources` calls.
   - evaluation runs.
   - metrics, logs, and traces emitted through OTLP.
   - continuous profiling with trace-to-profile correlation.
8. Use barriers and bounded work queues so tests create real overlapping work without depending on timing-only sleeps. Protect application-owned shared mutable state with explicit synchronization primitives.
9. Verify correctness under concurrency:
   - no crashes, deadlocks, data races visible through incorrect results, duplicate final writes, or lost updates.
   - corpus eligibility, redaction, citation, index-version, and transaction boundaries remain correct.
   - every completed operation has expected telemetry and correlation identifiers.
   - profile samples include work from multiple worker threads and do not contain unsafe dynamic labels.
10. Verify the whole operations path after concurrent load:
   - metrics, logs, traces, and profiles are queryable from their backends.
   - Grafana data sources remain healthy.
   - a Tempo trace can navigate to its matching Pyroscope profile.
   - a database archive created after the workload restores successfully.
11. Run the test in GitHub Actions on a runner with at least two CPU cores. Keep external model providers disabled and use deterministic local fixtures.
12. Keep the normal Python 3.14 test job. The free-threaded job is an additional compatibility and concurrency gate, not a replacement.

## Tests And Checks

- Build the runtime and run `python -VV`.
- Run a startup assertion for `Py_GIL_DISABLED` and `sys._is_gil_enabled()` before and after all application and profiling imports.
- `mise run test:free-threaded`
- Repeat the concurrent workload enough times to expose ordering defects while keeping the runtime bounded.
- Query metrics, logs, traces, and profiles for the test service instance and verify cross-signal correlation.
- Verify `pyroscope.profile.id` appears on root spans and trace-to-profile navigation resolves the corresponding profile.
- Run the backup and restore smoke test after concurrent load.
- `mise run ci`

## Acceptance Criteria

- The integration test uses CPython 3.14 compiled for free threading and confirms the lock is disabled before and after importing all application and profiling dependencies.
- No dependency, including `pyroscope-io`, silently re-enables the lock.
- Multiple Python threads concurrently exercise ingestion, retrieval, MCP, evaluation, telemetry, and profiling without correctness failures, crashes, or deadlocks.
- Metrics, logs, and traces reach their configured backends through OTLP; profiles reach Pyroscope through Grafana Alloy.
- Root traces correlate with profiles in Grafana.
- A backup created after the concurrent workload restores successfully.
- The free-threaded integration test runs as an explicit local task and a CI gate while the normal interpreter test remains available.

## Suggested Commit Message

`test: validate free-threaded python runtime`
