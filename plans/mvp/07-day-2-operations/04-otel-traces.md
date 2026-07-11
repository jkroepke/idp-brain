# 7.4: OpenTelemetry Traces

## Goal

Add vendor-neutral tracing for request receipt, corpus eligibility, Weaviate operations, retrieval stages, outbound HTTP and gRPC calls, threaded work, MCP tools, evaluation, and optional model calls while keeping attributes sanitized.

## Prerequisites

- Step 7.1 provides the traces backend.
- Steps 7.2 and 7.3 provide metrics, logs, and correlation behavior.
- Phase 6 has removed SQLAlchemy and psycopg instrumentation.

## Files To Create Or Modify

- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/observability/tracing.py`
- `src/idp_brain/observability/instrumentation.py`
- Weaviate store and retrieval adapters
- MCP and evaluation entry points
- tracing, redaction, gRPC, HTTP, and thread-context tests

## Implementation Instructions

1. Add and lock supported OpenTelemetry instrumentation for:
   - threading.
   - urllib3 or the HTTP client used by the pinned Weaviate client.
   - gRPC client calls used by the pinned Weaviate client.
2. Configure one application-owned `TracerProvider` and OTLP exporter.
3. Add application spans:
   - `request.received`.
   - `corpus_eligibility.derive`.
   - `query_profile.select`.
   - `weaviate.object_fetch`.
   - `weaviate.batch_write`.
   - `retrieval.exact_lookup`.
   - `retrieval.hybrid`.
   - `retrieval.structured_lookup`.
   - `retrieval.reranking`.
   - `retrieval.evidence_packaging`.
   - MCP tool spans.
   - `eval.run`.
   - optional `model.call`.
4. Use bounded attributes such as operation type, query profile, target vector, result count, collection generation, outcome, and sanitized error class.
5. Never capture raw queries, chunks, object bodies, vectors, filters, provider headers, API keys, URL query strings, request bodies, response bodies, or hidden policy values.
6. Instrument repository-owned Weaviate adapter methods manually so traces remain stable even if client internals change.
7. Configure HTTP and gRPC client instrumentation only for transport visibility. Prevent duplicate spans when manual and transport spans represent the same logical operation by using clear parent-child naming.
8. Exclude OTLP, Pyroscope, backend health, and other telemetry destinations from HTTP/gRPC instrumentation.
9. Configure `ThreadingInstrumentor` before threads and executors are created.
10. Verify context propagation through `Thread`, `Timer`, and `ThreadPoolExecutor`.
11. Strip URL query parameters and captured headers from outbound HTTP spans.
12. Do not capture gRPC message payloads or metadata containing credentials.
13. Initialize and uninitialize contrib instrumentation idempotently in tests.
14. Record sanitized exception types and safe status only.
15. Export traces through Alloy, not directly to Tempo.

## Tests And Checks

- Run tracing and redaction tests with an in-memory exporter.
- Verify manual Weaviate spans and transport child spans are not duplicated.
- Verify HTTP query strings, headers, bodies, gRPC messages, metadata, object content, vectors, and API keys are absent.
- Verify context propagation through threads and executors.
- Run CLI, MCP, and evaluation fixtures with the local stack.
- Verify traces correlate with logs and metrics.
- `mise run ci`

## Acceptance Criteria

- Weaviate, retrieval, MCP, evaluation, HTTP, gRPC, and threaded paths emit expected context.
- SQL database instrumentation is absent.
- Trace attributes are bounded and sanitized.
- Tests do not require an external collector.
- Traces flow through Alloy and correlate with logs and metrics.

## Suggested Commit Message

`feat: add weaviate opentelemetry traces`
