# 5.11: OpenTelemetry Spans

## Goal
Add vendor-neutral OpenTelemetry tracing for request receipt, access-context derivation, retrieval stages, MCP tools, eval runs, and optional LLM calls while keeping trace attributes sanitized.

## Prerequisites
- Steps 5.2 through 5.7 have added CLI and MCP retrieval paths.
- Step 5.8 has added eval execution.
- `ARCHITECTURE.md` remains the source of truth for required spans and observability safety.
- OpenTelemetry SDK and exporter dependencies are available through `pyproject.toml` and `uv.lock`.

## Files To Create Or Modify
- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/observability/__init__.py`
- `src/idp_brain/observability/tracing.py`
- `src/idp_brain/retrieval/service.py`
- `src/idp_brain/retrieval/explain.py`
- `src/idp_brain/mcp/server.py`
- `src/idp_brain/mcp/tools.py`
- `src/idp_brain/evaluation/runner.py`
- `src/idp_brain/settings.py`
- `tests/observability/test_tracing.py`
- `tests/observability/test_trace_redaction.py`

## Implementation Instructions
1. Configure OpenTelemetry through application settings with defaults safe for local development:
   - tracing disabled or console/in-memory by default in tests.
   - OTLP endpoint configurable by environment or `config/observability.yaml` if that file exists.
   - service name `idp-brain`.
2. Add spans named:
   - `request.received`
   - `access_context.derive`
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
3. Use low-cardinality sanitized attributes such as query profile, source type count, requested source count, bounded result count, active index version, retrieval mode, redaction status, access-filter result, error class, and latency.
4. Do not add raw queries, raw chunks, raw source text, secret-like values, PII, embedding vectors, SQL text, SQL parameters, provider request payloads, provider response bodies, full prompts, or hidden ACL group membership as span attributes or events.
5. Record exceptions with sanitized error class and safe message only.
6. Propagate correlation IDs across CLI retrieval, MCP tool calls, eval runs, retrieval events, logs, and metrics.
7. Keep deterministic tests by using the OpenTelemetry in-memory span exporter.

## Tests And Checks
- `uv run pytest tests/observability/test_tracing.py tests/observability/test_trace_redaction.py`
- `uv run idp-brain retrieve query "fixture query" --json`
- `uv run idp-brain eval run --cases tests/evaluation/fixtures/retrieval_cases.yaml --diagnostic-only`
- `mise run ci`
- Tests must verify required span names, parent/child relationships, sanitized attributes, exception redaction, correlation IDs, disabled tracing behavior, and absence of raw chunks, SQL, vectors, secrets, PII, and provider payloads.

## Acceptance Criteria
- Retrieval, MCP, and eval paths emit the required OpenTelemetry spans when tracing is enabled.
- Trace attributes and events are sanitized and bounded.
- Tests use an in-memory exporter and pass without an external collector.
- Observability does not change retrieval behavior or bypass access, redaction, citation, or safety rules.

## Suggested Commit Message
`feat: add retrieval opentelemetry spans`
