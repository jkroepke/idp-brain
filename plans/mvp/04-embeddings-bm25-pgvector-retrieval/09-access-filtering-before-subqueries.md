# 4.9: Access Filtering Before Subqueries

## Goal
Centralize trusted access, source, sensitivity, license, version, active-index, and relationship filtering so every retrieval subquery runs against an already-filtered scope.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Steps 4.5, 4.6, and 4.7 have local filter handling that can be replaced or routed through a shared helper.
- Phase 2 has access policy models and source visibility configuration.
- Phase 3 stores visibility label, sensitivity class, license policy status, redaction status, source ID, version metadata, and active/tombstone state on retrievable records.
- Normalized PostgreSQL relationship records link retrievable chunks, entities, claims, versions, dependencies, conflicts, or impact targets without embedding raw source text.
- Caller-provided context is treated only as a hint, not a trusted access decision.

## Files To Create Or Modify
- `src/idp_brain/retrieval/access_filters.py`
- `src/idp_brain/retrieval/models.py`
- `src/idp_brain/retrieval/exact.py`
- `src/idp_brain/retrieval/bm25.py`
- `src/idp_brain/retrieval/vector.py`
- `src/idp_brain/db/repositories/retrieval.py`
- `tests/retrieval/test_access_filtering.py`
- `tests/retrieval/test_filtering_before_subqueries.py`

## Implementation Instructions
1. Implement a `TrustedAccessContext` derived from local configuration, session identity, or operator policy. Do not trust MCP `caller_context_hint`, CLI free-form flags, or query text as authority.
2. Implement `RetrievalFilterSet` with source IDs, source types, version or release range, time range, visibility labels, allowed groups or principals, sensitivity classes, license policy statuses, redaction status, and active index version.
3. Implement `build_filtered_chunk_scope(context, filters, profile)` that returns a SQLAlchemy selectable or CTE containing only chunk IDs and sanitized metadata allowed for the request.
4. Require exact, BM25, vector, relationship, memory, diagnostics, and future MCP fetch/search paths to accept a filtered scope instead of querying `chunks` directly.
5. Apply filters in SQL before exact predicates, BM25 predicates, vector joins, relationship traversal, memory lookup, counts, snippets, diagnostics, and reranker payload construction.
6. Include license filtering before retrieval. Disallowed, unknown-disallowed, or policy-failed license statuses must not appear in candidates unless the active policy explicitly allows them.
7. Include sensitivity filtering before retrieval. Higher sensitivity classes must be excluded unless the trusted access context permits them.
8. Include source allowlist filtering before retrieval. User-requested source IDs narrow the trusted allowlist; they must not expand it.
9. Exclude chunks with failed redaction, failed policy checks, tombstones, inactive index versions, or missing citations.
10. Add `build_filtered_relationship_scope(context, filters, profile, filtered_chunk_scope)` for normalized PostgreSQL relationship rows. It must join relationship endpoints back to the already-filtered chunk or entity scope before traversal and must not expose edges connected only to unauthorized, source-disallowed, sensitivity-disallowed, license-disallowed, inactive, or uncited records.
11. Bound relationship traversal in SQL using profile settings for allowed relationship types, direction, maximum depth, maximum fanout per seed, maximum candidates, and cycle prevention. Recursive CTEs must carry depth and visited IDs and stop at the configured limits.
12. Add helper methods for filtered citation, claim, entity, and relationship scopes so conflict, lineage, dependency, impact, and evidence retrieval cannot bypass chunk filtering.
13. Make diagnostics report only post-filter counts by default. If pre-filter counts are needed for operations, guard them behind an admin-only diagnostic path and never expose them through normal CLI or MCP retrieval.
14. Update candidate retrievers from Steps 4.5 through 4.7 and the hybrid service from Step 4.10 to use the shared filtered scope and remove duplicate local filter logic.

## Tests And Checks
- `uv run pytest tests/retrieval/test_access_filtering.py`
- `uv run pytest tests/retrieval/test_filtering_before_subqueries.py`
- Test that exact, BM25, and vector retrievers cannot be constructed without a filtered scope or trusted context.
- Test that source allowlists narrow access and never expand server-derived rights.
- Test that disallowed sensitivity, license, redaction, inactive index, tombstone, and missing-citation rows are filtered before subqueries.
- Test that relationship traversal sees only normalized relationship rows whose source and target endpoints are inside filtered scopes.
- Test that relationship recursion stops at configured depth, fanout, candidate, type, direction, and cycle limits.
- Test that diagnostics and candidate counts do not include unauthorized rows.
- Test that MCP-style caller hints do not grant access.

## Acceptance Criteria
- All retrieval paths use a shared filter implementation before candidate generation.
- Raw table access from exact, BM25, vector, relationship, memory, diagnostics, CLI, and MCP retrieval paths is prevented by code structure and tests.
- Source, ACL, sensitivity, license, redaction, version, and active-index filters are enforced in SQL.
- Relationship traversal cannot expand access, leak unauthorized edge existence, or bypass source, ACL, sensitivity, license, redaction, citation, version, and active-index filters.
- Diagnostics do not leak existence or counts of unauthorized chunks.
- The safety rule that filters run before subqueries is directly regression-tested.

## Suggested Commit Message
`feat: enforce retrieval filters before subqueries`
