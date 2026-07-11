# 6.3: OpenTelemetry Logging

## Goal

Keep structured local logs while exporting one sanitized OpenTelemetry copy and recording uncaught process, thread, and asyncio task failures.

## Dependencies

- https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/logging/logging.html
- https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/exceptions/exceptions.html

Add and lock:

- `opentelemetry-instrumentation-logging`
- `opentelemetry-instrumentation-exceptions`

## Instructions

- initialize `LoggingInstrumentor` early for trace-context injection
- do not let instrumentation own the application formatter or call `logging.basicConfig()`
- keep exactly one local handler and one OpenTelemetry export path
- register `UnhandledExceptionInstrumentor` exactly once
- preserve sanitized local exception visibility
- make setup and teardown idempotent
- use bounded non-blocking queues and bounded shutdown
- never log raw queries, chunks, vectors, object payloads, provider payloads, secrets, credentials, or PII

## Checks

- trace and span identifiers are injected inside an active span
- process, thread, and asyncio failures produce one local and one exported sanitized record
- backend failure does not block application work
- duplicate handler and recursion tests pass
- `mise run ci`

## Acceptance Criteria

Logs remain useful without a backend and correlate safely with traces when export is enabled.
