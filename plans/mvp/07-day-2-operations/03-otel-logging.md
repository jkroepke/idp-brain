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

1. Add and lock `opentelemetry-instrumentation-logging` and `opentelemetry-instrumentation-exceptions`.
2. Configure two output paths:
   - a structured standard-output handler that is always present.
   - exactly one OpenTelemetry handler when export is enabled.
3. Use `LoggingInstrumentor` early with trace-context injection and without taking ownership of the application's formatter.
4. Choose one export-handler installation path and prevent duplicate records.
5. Keep code-location attributes disabled by default.
6. Register `UnhandledExceptionInstrumentor` once for process, thread, and asyncio failures.
7. Preserve a separate sanitized local exception path.
8. Keep standard output working when Alloy or another backend is unavailable.
9. Use bounded fields such as timestamp, severity, logger, event, service, environment, trace ID, span ID, outcome, operation, and sanitized error class.
10. Preserve machine-readable CLI output separation.
11. Apply redaction before either handler receives the record.
12. Never log raw source text, chunks, queries, Weaviate object payloads, filters, vectors, API keys, provider payloads, secrets, credentials, or PII.
13. Record sanitized error class and safe message only. Sanitize stack traces before export.
14. Use bounded non-blocking queues and flush with a bounded shutdown timeout.
15. Make setup and shutdown idempotent for tests and repeated CLI calls.

## Tests And Checks

- Run logging, redaction, and exception instrumentation tests.
- Run retrieval with the backend disabled and enabled.
- Verify exactly one local and one exported record.
- Trigger deterministic uncaught process, thread, and asyncio failures.
- Verify no duplicate handlers or recursive logging loops.
- `mise run ci`

## Acceptance Criteria

- Logs remain available locally without telemetry backends.
- Sanitized structured logs are exported once through OTLP when enabled.
- Trace context is injected without changing command output.
- Backend failures do not block application work.
- No sensitive retrieval or Weaviate payload appears in logs.

## Suggested Commit Message

`feat: add opentelemetry logging`
