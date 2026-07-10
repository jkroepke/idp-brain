# 6.4: OpenTelemetry Traces

## Goal

Add vendor-neutral OpenTelemetry tracing for request receipt, corpus eligibility derivation, retrieval stages, database access, outbound HTTP calls, threaded work, MCP tools, eval runs, and optional LLM calls while keeping trace attributes sanitized.

## Prerequisites

- Step 6.1 has added the local OTLP gateway and traces backend.
- Steps 6.2 and 6.3 have established shared resource attributes and correlation behavior for metrics and logs.
- Steps 5.2 through 5.7 have added CLI and MCP retrieval paths.
- Step 5.8 has added eval execution.
- `ARCHITECTURE.md` remains the source of truth for required spans and observability safety.

## Files To Create Or Modify

- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/observability/__init__.py`
- `src/idp_brain/observability/tracing.py`
- `src/idp_brain/observability/instrumentation.py`
- `src/idp_brain/retrieval/service.py`
- `src/idp_brain/retrieval/explain.py`
- `src/idp_brain/mcp/server.py`
- `src/idp_brain/mcp/tools.py`
- `src/idp_brain/evaluation/runner.py`
- `src/idp_brain/settings.py`
- `tests/observability/test_tracing.py`
- `tests/observability/test_trace_redaction.py`
- `tests/observability/test_database_instrumentation.py`
- `tests/observability/test_thread_context.py`
- `tests/observability/test_urllib3_instrumentation.py`

## Implementation Instructions

1. Add and lock these OpenTelemetry Python contrib packages through the normal `uv` workflow:
   - `opentelemetry-instrumentation-sqlalchemy`.
   - `opentelemetry-instrumentation-threading`.
   - `opentelemetry-instrumentation-urllib3`.
   - `opentelemetry-instrumentation-psycopg2`.
2. Configure OpenTelemetry through application settings with defaults safe for local development:
   - tracing disabled or console/in-memory by default in tests.
   - OTLP endpoint configurable by standard environment variables or `config/observability.yaml` if that file exists.
   - service name `idp-brain`.
3. Add application spans named:
   - `request.received`
   - `corpus_eligibility.derive`
   - `query_profile.select`
   - `retrieval.exact_lookup`
   - `retrieval.bm25`
   - `retrieval.vector`
   - `retrieval.relationship_traversal`
   - `retrieval.fusion`
   - `retrieval.reranking`
   - `retrieval.evidence_packaging`
   - `mcp.search`
   - `mcp.fetch`
   - `mcp.explain_search`
   - `mcp.list_sources`
   - `eval.run`
   - `llm.call`, only when an optional LLM call exists.
4. Use low-cardinality sanitized attributes such as query profile, source type count, requested source count, bounded result count, active index version, retrieval mode, redaction status, corpus eligibility filter result, error class, and latency.
5. Do not add raw queries, raw chunks, raw source text, secret-like values, PII, embedding vectors, SQL text, SQL parameters, provider request payloads, provider response bodies, full prompts, URL query strings, request or response bodies, captured headers, or pre-filter eligibility details as span attributes or events.
6. Configure `SQLAlchemyInstrumentor` for application-owned SQLAlchemy engines:
   - instrument each synchronous engine explicitly.
   - for async SQLAlchemy engines, instrument the corresponding `sync_engine`.
   - initialize instrumentation after the tracer provider exists and before the engine handles application queries.
   - keep SQLCommenter disabled by default.
   - do not enable SQL comment capture in `db.statement` or `db.query.text`.
   - apply a sanitizing span processor or hooks that remove SQL statement text and parameters if the instrumentation version emits them by default.
7. Configure `Psycopg2Instrumentor` only for direct psycopg2 connections that bypass SQLAlchemy. Do not globally enable both SQLAlchemy and psycopg2 instrumentation for the same connection path, because that creates duplicate database spans.
8. If direct psycopg2 instrumentation is enabled:
   - prefer per-connection instrumentation when practical.
   - keep SQLCommenter disabled.
   - remove SQL text, parameters, credentials, and unbounded database object names from spans.
   - verify database errors expose only sanitized exception type and safe status.
9. Keep application database tracing separate from the collector-side PostgreSQL receiver in Steps 6.1 and 6.2. The receiver produces database metrics; SQLAlchemy and psycopg2 instrumentation produce application client spans. Do not try to infer query text from receiver events or join on raw SQL.
10. Configure `ThreadingInstrumentor` once before application threads, timers, or `ThreadPoolExecutor` workers are created. It propagates the active OpenTelemetry context across threads but must not create standalone spans.
11. Verify context propagation through `threading.Thread`, `threading.Timer`, and `concurrent.futures.ThreadPoolExecutor`. Child work must remain linked to the parent trace without sharing unsafe mutable context.
12. Configure `URLLib3Instrumentor` for outbound urllib3 requests:
    - use a URL filter that strips query parameters before span attributes are created.
    - configure an exclude list for Alloy OTLP endpoints, the Pyroscope profile receiver, backend health checks, and other internal telemetry destinations to avoid recursive self-observability.
    - do not capture request or response headers by default.
    - do not capture request or response bodies.
    - allow only scheme, normalized host, port, HTTP method, status, and a bounded route or path template.
    - use request and response hooks only for additional sanitization or bounded attributes.
13. Initialize every contrib instrumentor idempotently and uninstrument it during isolated tests when required. Repeated CLI invocations in one process must not stack wrappers or duplicate spans.
14. Record exceptions on spans with sanitized error class and safe message only. Uncaught process, thread, and asyncio exceptions are handled by the logging instrumentation from Step 6.3 and must correlate with the active trace when context exists.
15. Propagate correlation IDs and trace context across CLI retrieval, MCP tool calls, eval runs, database calls, outbound HTTP calls, threaded work, retrieval events, logs, and metrics.
16. Export traces through OTLP to Alloy when enabled. Do not send application telemetry directly to the traces backend.
17. Keep deterministic tests by using the OpenTelemetry in-memory span exporter.

## Tests And Checks

- `uv run pytest tests/observability/test_tracing.py tests/observability/test_trace_redaction.py`
- `uv run pytest tests/observability/test_database_instrumentation.py tests/observability/test_thread_context.py tests/observability/test_urllib3_instrumentation.py`
- Verify SQLAlchemy-managed queries create one sanitized database span per operation.
- Verify a direct psycopg2 fixture path creates one sanitized database span and is not simultaneously wrapped by SQLAlchemy instrumentation.
- Verify no database span contains statement text, parameters, SQL comments, credentials, source rows, or unbounded object names.
- Verify active context propagates through `Thread`, `Timer`, and `ThreadPoolExecutor` and that the threading instrumentation creates no standalone telemetry.
- Verify urllib3 spans strip URL query strings, omit headers and bodies, and exclude local telemetry endpoints.
- Verify instrumentation setup is idempotent and does not duplicate spans after repeated initialization.
- `uv run idp-brain retrieve query "fixture query" --json`
- `uv run idp-brain eval run --cases tests/evaluation/fixtures/retrieval_cases.yaml --diagnostic-only`
- With the local stack running, confirm a fixture trace is queryable and linked to its logs and metrics in Grafana.
- `mise run ci`
- Tests must verify required span names, parent/child relationships, sanitized attributes, exception redaction, correlation IDs, disabled tracing behavior, and absence of raw chunks, SQL, vectors, secrets, PII, headers, bodies, URL queries, and provider payloads.

## Acceptance Criteria

- Retrieval, MCP, eval, database, outbound HTTP, and threaded paths emit or propagate the expected OpenTelemetry trace context when tracing is enabled.
- SQLAlchemy instrumentation covers ORM-managed engines, while psycopg2 instrumentation is limited to direct connections and never duplicates the same database operation.
- Collector-side PostgreSQL receiver metrics and application-side database spans remain separate, complementary telemetry paths.
- Threading instrumentation propagates context through standard threads, timers, and thread-pool workers without generating standalone telemetry.
- urllib3 instrumentation creates sanitized outbound HTTP spans and excludes the observability pipeline itself.
- Trace attributes and events are sanitized and bounded.
- Tests use an in-memory exporter and pass without an external collector.
- Traces are exported through the shared OTLP gateway and correlate with logs and metrics.
- Observability does not change retrieval behavior or bypass corpus eligibility, redaction, citation, or safety rules.

## Suggested Commit Message

`feat: add retrieval opentelemetry traces`
