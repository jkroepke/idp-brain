# 7.3: OpenTelemetry Logging

## Goal

Add structured OpenTelemetry logging exported through OTLP while keeping application logs available on standard output, with trace-context injection and coverage for uncaught process, thread, and asyncio exceptions.

## Prerequisites

- Step 7.1 provides the OTLP gateway and logs backend.
- Step 7.2 defines shared resource attributes and correlation identifiers.
- Existing commands and workers use Python logging or can migrate without changing user-visible output.

## Files To Create Or Modify

- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/observability/logging.py`
- `src/idp_brain/observability/instrumentation.py`
- `src/idp_brain/settings.py`
- CLI, MCP, ingestion, retrieval, evaluation, and migration entry points
- logging and redaction tests

## Implementation Instructions

1. Add and lock:
   - [`opentelemetry-instrumentation-logging`](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/logging/logging.html).
   - [`opentelemetry-instrumentation-exceptions`](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/exceptions/exceptions.html).
2. Configure two output paths:
   - a structured standard-output handler that is always present.
   - exactly one OpenTelemetry handler when export is enabled.
3. Initialize `LoggingInstrumentor` early with trace-context injection enabled and without taking ownership of the application's formatter or calling `logging.basicConfig()`.
4. Choose one export-handler installation path and prevent duplicate records when logging instrumentation and application setup run together.
5. Keep code-location attributes disabled by default.
6. Register `UnhandledExceptionInstrumentor` exactly once for uncaught process, thread, and asyncio task failures.
7. Preserve a separate sanitized local exception path. OpenTelemetry exception instrumentation must not suppress Python's normal local failure visibility.
8. Keep standard output working when Alloy or another backend is unavailable.
9. Use bounded fields such as timestamp, severity, logger, event, service, environment, trace ID, span ID, outcome, operation, and sanitized error class.
10. Preserve machine-readable CLI output separation.
11. Apply redaction before either handler or exception instrumentation receives the record.
12. Never log raw source text, chunks, queries, Weaviate object payloads, filters, vectors, API keys, provider payloads, secrets, credentials, or PII.
13. Record sanitized error class and safe message only. Sanitize stack traces before local output or export.
14. Use bounded non-blocking queues and flush with a bounded shutdown timeout.
15. Make setup, shutdown, instrumentation, and uninstrumentation idempotent for tests and repeated CLI calls.

## Tests And Checks

- Run logging, redaction, and exception instrumentation tests.
- Verify `LoggingInstrumentor` injects trace and span identifiers inside an active span without changing the application formatter.
- Run retrieval with the backend disabled and enabled.
- Verify exactly one local and one exported record.
- Trigger deterministic uncaught process, thread, and asyncio task failures in isolated subprocess tests.
- Verify `UnhandledExceptionInstrumentor` produces sanitized OpenTelemetry exception records while local exception output remains available.
- Verify no duplicate handlers, duplicate exception records, or recursive logging loops.
- `mise run ci`

## Acceptance Criteria

- Logs remain available locally without telemetry backends.
- Sanitized structured logs are exported once through OTLP when enabled.
- `LoggingInstrumentor` injects trace context without changing command output or formatter ownership.
- `UnhandledExceptionInstrumentor` covers uncaught process, thread, and asyncio task failures without suppressing local visibility.
- Backend failures do not block application work or exception handling.
- No sensitive retrieval or Weaviate payload appears in logs.

## Suggested Commit Message

`feat: add opentelemetry logging`
