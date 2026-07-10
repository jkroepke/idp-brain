# 6.3: OpenTelemetry Logging

## Goal
Add structured OpenTelemetry logging exported through OTLP while keeping every application log available on standard output.

## Prerequisites
- Step 6.1 has added the local OTLP gateway and logs backend.
- Step 6.2 has established shared OpenTelemetry resource attributes and correlation identifiers.
- Existing commands and workers already use the Python logging package or can be migrated without changing user-visible command output.
- `ARCHITECTURE.md` remains the source of truth for redaction and telemetry safety.

## Files To Create Or Modify
- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/observability/logging.py`
- `src/idp_brain/observability/__init__.py`
- `src/idp_brain/settings.py`
- CLI, MCP, ingestion, retrieval, and evaluation entry points that initialize logging
- `tests/observability/test_logging.py`
- `tests/observability/test_log_redaction.py`

## Implementation Instructions
1. Configure standard Python logging with two independent handlers:
   - a structured standard-output handler that is always present.
   - an OpenTelemetry logging handler that exports through OTLP when enabled.
2. Standard output remains the operational fallback and must continue to work when Alloy or any backend is unavailable.
3. Use structured records with bounded fields such as timestamp, severity, logger name, event name, service name, service version, deployment environment, correlation ID, trace ID, span ID, outcome, and sanitized error class.
4. Preserve normal CLI output separation. Human or JSON command results stay on standard output as defined by each command; diagnostic logs must use the configured logging stream without corrupting machine-readable output.
5. Apply redaction before a record reaches either handler. Do not rely on backend filtering.
6. Never log raw source text, raw chunks, raw queries, prompts, SQL text or parameters, embeddings, provider payloads, secrets, credentials, PII, or pre-filter eligibility details.
7. Record exceptions with a sanitized error class and safe message. Stack traces may be emitted only when they do not include sensitive local values; tests must cover the sanitizer.
8. Attach active trace and span identifiers automatically when a span context exists.
9. Use bounded queues and non-blocking export behavior so telemetry outages do not block ingestion, retrieval, MCP calls, or evaluation.
10. Flush the OTLP logging provider during orderly process shutdown while keeping a bounded timeout.

## Tests And Checks
- `uv run pytest tests/observability/test_logging.py tests/observability/test_log_redaction.py`
- Run a CLI retrieval with the backend disabled and verify logs still appear on standard output or the configured diagnostic stream.
- Run the same retrieval with the local stack enabled and verify the log record is present both locally and in the logs backend.
- Confirm trace and span identifiers appear on records created inside an active span.
- `mise run ci`

## Acceptance Criteria
- Every application log remains available locally without a telemetry backend.
- The same sanitized structured records are exported through OTLP when enabled.
- Log records correlate with traces through trace and span identifiers.
- Backend failures do not block application work.
- Raw unsanitized chunks, queries, SQL, secrets, PII, vectors, prompts, and provider payloads never appear in either output path.

## Suggested Commit Message
`feat: add opentelemetry logging`
