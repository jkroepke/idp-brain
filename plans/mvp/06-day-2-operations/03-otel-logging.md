# 6.3: OpenTelemetry Logging

## Goal

Add structured OpenTelemetry logging exported through OTLP while keeping every application log available on standard output, with trace-context injection and coverage for uncaught process, thread, and asyncio exceptions.

## Prerequisites

- Step 6.1 has added the local OTLP gateway and logs backend.
- Step 6.2 has established shared OpenTelemetry resource attributes and correlation identifiers.
- Existing commands and workers already use the Python logging package or can be migrated without changing user-visible command output.
- `ARCHITECTURE.md` remains the source of truth for redaction and telemetry safety.

## Files To Create Or Modify

- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/observability/logging.py`
- `src/idp_brain/observability/instrumentation.py`
- `src/idp_brain/observability/__init__.py`
- `src/idp_brain/settings.py`
- CLI, MCP, ingestion, retrieval, and evaluation entry points that initialize logging
- `tests/observability/test_logging.py`
- `tests/observability/test_log_redaction.py`
- `tests/observability/test_exception_instrumentation.py`

## Implementation Instructions

1. Add and lock:
   - `opentelemetry-instrumentation-logging`.
   - `opentelemetry-instrumentation-exceptions`.
2. Configure standard Python logging with two output paths:
   - a structured standard-output handler that is always present.
   - exactly one OpenTelemetry logging handler that exports through OTLP when enabled.
3. Use `LoggingInstrumentor` early in process startup with trace-context injection enabled and `set_logging_format=False`, because the application owns its structured JSON formatter. Do not let the instrumentation call `logging.basicConfig()` or replace the standard-output handler.
4. Choose exactly one OpenTelemetry export-handler installation path. Prefer the handler supplied by `opentelemetry-instrumentation-logging`; if the application installs the handler explicitly, disable the package's automatic handler to prevent duplicate exported records.
5. Keep code-location attributes disabled by default. File paths and line information may expose local paths and increase cardinality; enable them only through an explicit reviewed setting.
6. Register `UnhandledExceptionInstrumentor` once during startup. It emits OpenTelemetry logs for uncaught process exceptions, uncaught `threading` exceptions, and unhandled asyncio task exceptions.
7. Keep Python's local exception visibility as a separate sanitized standard-output path. Do not assume the OpenTelemetry exception log is automatically mirrored into standard Python logging, and avoid duplicate local or remote records when the default exception hooks and the instrumentor observe the same failure.
8. Standard output remains the operational fallback and must continue to work when Alloy or any backend is unavailable.
9. Use structured records with bounded fields such as timestamp, severity, logger name, event name, service name, service version, deployment environment, correlation ID, trace ID, span ID, trace sampled state, outcome, and sanitized error class.
10. Preserve normal CLI output separation. Human or JSON command results stay on standard output as defined by each command; diagnostic logs must use the configured logging stream without corrupting machine-readable output.
11. Apply redaction before a record reaches either handler or the unhandled-exception instrumentation. Do not rely on backend filtering.
12. Never log raw source text, raw chunks, raw queries, prompts, SQL text or parameters, embeddings, provider payloads, secrets, credentials, PII, or pre-filter eligibility details.
13. Record exceptions with a sanitized error class and safe message. Stack traces may be emitted only after sanitization and must not include sensitive local values, SQL, source content, credentials, environment secrets, or request payloads.
14. Use bounded queues and non-blocking export behavior so telemetry outages do not block ingestion, retrieval, MCP calls, evaluation, or exception handling.
15. Flush the OpenTelemetry logging provider during orderly process shutdown with a bounded timeout. Instrumentation initialization and shutdown must be idempotent for tests and repeated CLI invocations.

## Tests And Checks

- `uv run pytest tests/observability/test_logging.py tests/observability/test_log_redaction.py tests/observability/test_exception_instrumentation.py`
- Run a CLI retrieval with the backend disabled and verify logs still appear on standard output or the configured diagnostic stream.
- Run the same retrieval with the local stack enabled and verify the log record is present once locally and once in the logs backend.
- Confirm `LoggingInstrumentor` injects trace ID, span ID, service name, and sampled state into records created inside an active span without changing the application's formatter.
- Trigger deterministic uncaught process, thread, and asyncio task exceptions in isolated subprocess tests and verify one sanitized local record plus one OpenTelemetry exception log.
- Verify code-location attributes are disabled by default.
- Verify no duplicate handler, duplicate exception record, or recursive logging loop is introduced.
- `mise run ci`

## Acceptance Criteria

- Every application log remains available locally without a telemetry backend.
- The same sanitized structured records are exported through OTLP when enabled.
- `opentelemetry-instrumentation-logging` injects trace context without taking ownership of the application's standard-output format.
- `opentelemetry-instrumentation-exceptions` covers uncaught process, thread, and asyncio task exceptions as OpenTelemetry logs while the application preserves separate local visibility.
- Log records correlate with traces through trace and span identifiers.
- Backend failures do not block application work or uncaught-exception handling.
- Raw unsanitized chunks, queries, SQL, secrets, PII, vectors, prompts, provider payloads, and sensitive stack-local values never appear in either output path.

## Suggested Commit Message

`feat: add opentelemetry logging`
