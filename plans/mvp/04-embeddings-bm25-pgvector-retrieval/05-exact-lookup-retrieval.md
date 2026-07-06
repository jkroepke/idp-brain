# 4.5: Exact Lookup Retrieval

## Goal
Implement exact and near-exact candidate retrieval for identifiers, symbols, paths, endpoint paths, fields, versions, and error strings using PostgreSQL indexes over sanitized metadata.

## Prerequisites
- Phase 3 has persisted sanitized chunks, citations, source metadata, symbol metadata, and version metadata.
- Phase 4 migrations for supporting exact indexes are present or planned.
- Access, source, sensitivity, license, and version constraints are available from configuration and request context.
- Retrieval returns candidates, not final evidence bundles, until later steps fuse and package results.

## Files To Create Or Modify
- `src/idp_brain/retrieval/__init__.py`
- `src/idp_brain/retrieval/models.py`
- `src/idp_brain/retrieval/exact.py`
- `src/idp_brain/retrieval/query_intent.py`
- `src/idp_brain/db/repositories/retrieval.py`
- `alembic/versions/<revision>_chunks_exact_lookup_indexes.py`
- `tests/retrieval/test_exact_lookup.py`
- `tests/db/test_exact_lookup_indexes.py`

## Implementation Instructions
1. Add exact lookup indexes for the fields named in `ARCHITECTURE.md`, starting with:
   ```sql
   CREATE INDEX chunks_exact_symbol_idx
   ON chunks (source_id, version_label, language, symbol_path)
   WHERE symbol_path IS NOT NULL;
   ```
2. Add additional B-tree or partial indexes for `artifact_path`, `heading_path`, `signature_text`, `source_type`, `version_label`, endpoint path or schema key fields if those columns exist.
3. Use `pg_trgm` only as a bounded fallback for typo-tolerant lookup when the query profile allows it. Exact matching must be attempted before fuzzy matching.
4. Define `RetrievalQuery`, `RetrievalFilters`, and `Candidate` models in `src/idp_brain/retrieval/models.py`. A candidate must include `chunk_id`, `retrieval_path`, `rank`, `matched_fields`, sanitized metadata, and optional diagnostics; it must not include raw chunk text.
5. Implement `ExactLookupRetriever.retrieve(query, filters, limit)` so it always applies trusted filters before lookup predicates. Until Step 4.9 centralizes filtering, build a local filtered CTE with source allowlist, ACL labels, sensitivity class, license policy status, active index version, and version scope.
6. Parse query intent conservatively in `query_intent.py` to identify probable symbols, paths, endpoint paths, flags, schema keys, version strings, quoted strings, and error constants. Do not hardcode one product domain.
7. Return exact candidates with deterministic ordering: exact field priority, authority rank, freshness, path specificity, chunk ID.
8. Do not return sanitized chunk excerpts from this step unless the candidate model already has an excerpt contract. Full evidence packaging belongs to Step 4.12.
9. Record diagnostics only after filters are applied. Do not report counts for unauthorized chunks.
10. Keep relationship traversal out of this step except for IDs needed by exact lookup; bounded traversal is handled by later retrieval work.

## Tests And Checks
- `mise run db:migrate`
- `uv run pytest tests/db/test_exact_lookup_indexes.py`
- `uv run pytest tests/retrieval/test_exact_lookup.py`
- Test exact symbol, artifact path, endpoint path, schema key, version string, and error-string lookups.
- Test that unauthorized, sensitivity-disallowed, source-disallowed, and license-disallowed chunks are excluded before lookup.
- Test that fuzzy fallback is disabled unless the query profile enables it.
- Test deterministic ordering when two chunks match the same identifier.
- Test that candidates contain IDs and sanitized metadata only.

## Acceptance Criteria
- Exact lookup works for code, docs, schema/API, release, and error-string queries without product-specific hardcoding.
- Trusted filters are applied before exact and fuzzy predicates.
- Exact lookup results are candidate records ready for fusion, not final LLM context.
- Raw unsanitized chunks are never returned, logged, or used in diagnostics.
- Supporting indexes are migration-managed and tested.

## Suggested Commit Message
`feat: add exact lookup retrieval`
