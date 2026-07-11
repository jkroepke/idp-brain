# 6.4: OpenTelemetry Traces

## Goal

Trace ingestion and Weaviate operations with stable application spans plus supported client and transport instrumentation.

## Dependencies

- https://pypi.org/project/opentelemetry-instrumentation-weaviate/
- https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/threading/threading.html
- https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/urllib/urllib.html

Add and lock:

- `opentelemetry-instrumentation-weaviate`
- `opentelemetry-instrumentation-threading`
- `opentelemetry-instrumentation-urllib`
- supported gRPC client instrumentation used by the pinned Weaviate client

## Instructions

1. Configure one application-owned `TracerProvider` and OTLP exporter.
2. Initialize `WeaviateInstrumentor` after the provider and before clients are created.
3. Initialize `ThreadingInstrumentor` before worker threads and executors.
4. Instrument `urllib` and gRPC only when used by the pinned dependency graph.
5. Keep stable manual spans around ingestion batches, collection bootstrap, direct retrieval, evaluation, and backup operations.
6. Treat Weaviate and transport spans as child spans, not duplicate logical operations.
7. Exclude OTLP, Pyroscope, health, and telemetry destinations.
8. Strip URL query strings and captured headers; never capture request bodies, response bodies, vectors, filters, object content, credentials, or gRPC messages.
9. Make instrumentation and uninstrumentation idempotent.

## Checks

- official Weaviate client calls create child client spans
- context propagates through `Thread`, `Timer`, and `ThreadPoolExecutor`
- `urllib` and gRPC spans are sanitized
- tests use an in-memory exporter
- no SQL database instrumentation exists
- `mise run ci`

## Acceptance Criteria

Application, Weaviate client, transport, and threaded spans are correlated without duplicate logical spans or sensitive payloads.
