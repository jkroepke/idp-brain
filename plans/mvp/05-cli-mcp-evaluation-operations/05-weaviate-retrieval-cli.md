# 5.5: Direct Weaviate Retrieval CLI

## Goal

Replace the application-owned retrieval orchestration with a thin CLI adapter over one direct Weaviate query.

Step 5.0 is normative. The legacy retrieval service is deletion input, not a feature checklist.

## Explicit Non-Requirements

The CLI does not need to preserve or reimplement:

- trusted corpus eligibility derivation at query time
- mandatory hidden source, visibility, sensitivity, license, version, active-state, or index-generation filters
- application exact, BM25, and vector subqueries
- reciprocal rank fusion
- authority or freshness score adjustments
- a separate citation-object fetch path
- evidence-bundle assembly or token-budget packaging
- `fetch` or `explain_search` behavior required by the old MCP plan

## Instructions

1. Keep `idp-brain retrieve query` as the operator and evaluation surface.
2. Resolve the configured validated `EvidenceChunk` collection generation.
3. Issue one Weaviate hybrid query through the official client.
4. Configure only the required target vector, lexical properties, `alpha`, result limit, returned properties, and bounded score metadata.
5. Return ranked sanitized chunks with citation properties directly.
6. Keep human and JSON output stable only where useful to callers; do not preserve the former evidence-bundle schema.
7. Use explicit collection or tenant selection when a caller is authorized for a specific evidence boundary.
8. Do not call the legacy exact, BM25, vector, fusion, reranker, corpus-filter, citation-fetcher, or evidence-assembler modules.
9. Do not introduce compatibility adapters for the old retrieval service or DTOs.
10. Defer UUID fetch and bounded search explanation until measured usage proves they are necessary.
11. Keep raw queries and content out of telemetry.

## Checks

- the CLI performs one direct Weaviate retrieval request
- returned objects contain sanitized content and citation properties
- BM25-only, vector-only, and hybrid modes can be selected for evaluation without application fusion
- no legacy retrieval orchestration is imported or invoked
- no application authority/freshness adjustment or evidence bundle is produced
- `mise run retrieve -- "fixture query"`
- `mise run ci`

## Acceptance Criteria

The retrieval CLI is a thin Weaviate client surface. It does not preserve the legacy retrieval architecture, custom evidence contract, or removed query-time policy features.
