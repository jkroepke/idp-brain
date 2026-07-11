# 7.4: OpenTelemetry Traces

## Goal

Add vendor-neutral tracing for request receipt, corpus eligibility, Weaviate client operations, retrieval stages, outbound HTTP and gRPC calls, threaded work, MCP tools, evaluation, and optional model calls while keeping attributes sanitized.

## Prerequisites

- Step 7.1 provides the traces backend.
- Steps 7.2 and 7.3 provide metrics, logs, exception handling, and correlation behavior.
- Phase 6 has removed SQLAlchemy and psycopg instrumentation.

## Files To Create Or Modify

- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/observability/tracing.py`
- `src/idp_brain/observability/instrumentation.py`
- Weaviate store and retrieval adapters
- MCP and evaluation entry points
- tracing, redaction, Weaviate, gRPC, HTTP, and thread-context tests

## Implementation Instructions

1. Add and lock supported OpenTelemetry instrumentation for:
   - [`opentelemetry-instrumentation-weaviate`](https://pypi.org/project/opentelemetry-instrumentation-weaviate/) for calls made through the official Weaviate Python client.
   - [`opentelemetry-instrumentation-threading`](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/threading/threading.html) for context propagation through Python threads and executors.
   - [`opentelemetry-instrumentation-urllib`](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/urllib/urllib.html) for outbound calls using `urllib`.
   - supported gRPC client instrumentation used by the pinned Weaviate client.
2. Configure one application-owned `TracerProvider` and OTLP exporter.
3. Initialize `WeaviateInstrumentor` after the `TracerProvider` exists and before application Weaviate clients are created. Pin and test the instrumentation against the exact Weaviate client version in `uv.lock`.
4. Add stable application spans:
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
5. Use bounded attributes such as operation type, query profile, target vector, result count, collection generation, outcome, and sanitized error class.
6. Never capture raw queries, chunks, object bodies, vectors, filters, provider headers, API keys, URL query strings, request bodies, response bodies, or hidden policy values.
7. Keep repository-owned manual spans around logical Weaviate adapter operations so application-level span names remain stable even when client internals or instrumentation change.
8. Treat spans emitted by `WeaviateInstrumentor` and HTTP/gRPC instrumentation as child client or transport spans. Do not replace the logical application span and do not create two spans for the same layer.
9. Configure `urllib` and gRPC client instrumentation only when those transports are used by the pinned dependency graph. Do not add unused instrumentors.
10. Exclude OTLP, Pyroscope, backend health, and other telemetry destinations from HTTP/gRPC instrumentation to prevent recursive telemetry.
11. Configure `ThreadingInstrumentor` before `Thread`, `Timer`, or `ThreadPoolExecutor` workers are created.
12. Verify context propagation through `Thread`, `Timer`, and `ThreadPoolExecutor`.
13. Strip URL query parameters and captured headers from outbound `urllib` spans. Do not capture request or response bodies.
14. Do not capture gRPC message payloads or metadata containing credentials.
15. Initialize and uninitialize all contrib instrumentation idempotently in tests and repeated CLI invocations.
16. Record sanitized exception types and safe status only.
17. Export traces through Alloy, not directly to Tempo.

## Tests And Checks

- Run tracing and redaction tests with an in-memory exporter.
- Verify `WeaviateInstrumentor` creates client spans for official Weaviate client operations.
- Verify each logical retrieval or ingestion operation has one manual application span, with Weaviate and transport spans below it rather than duplicated beside it.
- Verify the instrumentation works with the exact pinned Weaviate client version.
- Verify `urllib` query strings, headers, bodies, gRPC messages, metadata, object content, vectors, filters, and API keys are absent.
- Verify context propagation through `Thread`, `Timer`, and `ThreadPoolExecutor`.
- Verify instrumentation setup and teardown are idempotent.
- Run CLI, MCP, ingestion, migration, and evaluation fixtures with the local stack.
- Verify traces correlate with logs, exception records, metrics, and profiles.
- `mise run ci`

## Acceptance Criteria

- Official Weaviate Python client calls are covered by `opentelemetry-instrumentation-weaviate`.
- Stable manual application spans expose the logical retrieval and ingestion flow without duplicate client or transport spans.
- Weaviate, retrieval, MCP, evaluation, `urllib`, gRPC, and threaded paths emit expected context when used.
- SQL database instrumentation is absent.
- Trace attributes are bounded and sanitized.
- Tests do not require an external collector.
- Traces flow through Alloy and correlate with logs and metrics.

## Suggested Commit Message

`feat: add weaviate opentelemetry traces`
