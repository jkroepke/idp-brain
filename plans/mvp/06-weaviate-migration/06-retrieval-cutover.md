# 6.6: Hybrid, Exact, And Structured Retrieval

## Goal

Replace SQL, ParadeDB, pgvector, and application-owned rank fusion with a Weaviate retrieval adapter while preserving the existing CLI, MCP, and evidence contracts.

## Prerequisites

- Step 6.5 has populated an inactive Weaviate generation.
- Existing retrieval interfaces and evaluation fixtures are available.
- Query profiles define target vectors, lexical properties, filters, and hybrid weights.

## Files To Create Or Modify

- `src/idp_brain/retrieval/weaviate.py`
- `src/idp_brain/retrieval/service.py`
- `src/idp_brain/retrieval/exact.py`
- `src/idp_brain/retrieval/explain.py`
- `config/retrieval.yaml`
- CLI and MCP wiring
- retrieval tests

## Implementation Instructions

1. Implement a Weaviate-specific retriever behind the existing application retrieval service. Keep the interface focused on domain requests and evidence results, not generic backend compatibility.
2. Implement exact lookup in this order:
   - deterministic object fetch for known chunk, citation, source, or artifact IDs.
   - equality filters for stable symbols, paths, fields, endpoints, errors, versions, and checksums.
   - BM25F with semantic weight disabled for textual identifiers.
3. Implement normal candidate generation as one Weaviate hybrid query.
4. Configure per-profile:
   - active collection generation.
   - target named vector.
   - lexical query properties and weights.
   - hybrid alpha and fusion mode.
   - result limits and auto-cut behavior where supported.
   - score and explanation metadata.
5. Attach corpus eligibility filters to the Weaviate request before search execution.
6. Use Weaviate's fused hybrid order. Remove normal-path reciprocal rank fusion and score calibration from application code.
7. Deduplicate exact and hybrid results by stable chunk ID.
8. For lineage, claims, conflicts, and relationships:
   - use denormalized fields first.
   - use bounded structured collection queries or references only when required.
   - convert structured matches back to evidence chunk IDs.
9. Prefer a Weaviate-supported reranker integration. Keep the external reranker adapter only when it is required by a configured profile.
10. Map Weaviate score metadata and explanations into the existing safe diagnostics contract.
11. Preserve current CLI and MCP payload shapes unless a separate compatibility change is documented.
12. Keep a temporary shadow mode that executes both retrievers for evaluation but returns results from the configured primary path only.
13. Do not keep the old retriever as a fallback after the completion gate passes.

## Tests And Checks

- Run exact identifier, path, symbol, field, endpoint, version, and error lookups.
- Run BM25-only, vector-only, and hybrid profiles.
- Verify target named vectors are selected correctly.
- Verify filters are present on every query.
- Verify exact and hybrid duplicates collapse to one evidence item.
- Verify score diagnostics contain no vectors, source text, secrets, or hidden policy details.
- Run existing CLI and MCP retrieval tests against Weaviate.
- `mise run ci`

## Acceptance Criteria

- CLI and MCP can retrieve entirely through Weaviate.
- The normal path uses one Weaviate hybrid query instead of two database queries plus application fusion.
- Exact lookup and structured retrieval remain citation-backed.
- Query profiles control Weaviate behavior through configuration.
- The old backend exists only for temporary shadow evaluation.

## Suggested Commit Message

`feat: add weaviate retrieval path`
