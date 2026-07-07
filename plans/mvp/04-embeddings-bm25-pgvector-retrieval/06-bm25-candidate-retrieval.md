# 4.6: BM25 Candidate Retrieval

## Goal
Implement ParadeDB BM25 candidate retrieval over sanitized chunk text and profile-selected metadata fields.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Step 4.3 is complete.
- Step 4.5 has introduced shared retrieval query and candidate models.
- `chunks_bm25_idx` exists in local and CI integration databases.
- Query profiles define BM25 fields and candidate limits, or this step adds the temporary defaults that Step 4.8 formalizes.

## Files To Create Or Modify
- `src/idp_brain/retrieval/bm25.py`
- `src/idp_brain/retrieval/models.py`
- `src/idp_brain/db/repositories/retrieval.py`
- `tests/retrieval/test_bm25_retrieval.py`
- `tests/retrieval/test_bm25_sql.py`

## Implementation Instructions
1. Implement `BM25CandidateRetriever.retrieve(query, filters, profile, limit)` using ParadeDB `pg_search`.
2. Build BM25 queries only against sanitized fields selected by the active query profile, starting with `sanitized_text`, `heading_path`, `symbol_path`, `signature_text`, and `artifact_path`.
3. Apply trusted filters before BM25 predicates by querying through a filtered chunk scope or CTE. Until Step 4.9 centralizes this helper, keep the local implementation equivalent to Step 4.5.
4. Use the architecture query shape as the base:
   ```sql
   SELECT id, pdb.score(id) AS bm25_score
   FROM filtered_chunks
   WHERE sanitized_text ||| :query
   ORDER BY bm25_score DESC
   LIMIT :bm25_top_k;
   ```
5. If ParadeDB requires the BM25 predicate to reference the indexed table directly, structure the SQL so the filter predicates are still applied in the same subquery before candidates are exposed to application code.
6. Return candidates with `retrieval_path = "bm25"`, rank position, `bm25_score` as path-specific diagnostic metadata, matched fields when available, and no vector distance.
7. Do not compare `bm25_score` with exact ranks or vector distances. Score merging happens only in Step 4.10 through reciprocal-rank fusion or a configured calibrated method.
8. Add a deterministic test fallback that exercises query building and candidate shaping without `pg_search`. The product implementation must still fail clearly if BM25 retrieval is requested against a database missing ParadeDB.
9. Ensure logs include query length, profile ID, filtered candidate count, and latency only. Do not log full sensitive queries when policy marks them sensitive, and do not log chunk text.
10. Keep PostgreSQL native FTS as a diagnostic fallback only if explicitly implemented; do not make it the default BM25 path.

## Tests And Checks
- `uv run pytest tests/retrieval/test_bm25_sql.py`
- `uv run pytest tests/retrieval/test_bm25_retrieval.py -m requires_pg_search`
- Test that BM25 uses sanitized text and configured metadata fields only.
- Test that filtered-out chunks never appear in BM25 candidates or diagnostics.
- Test that `bm25_score` is present as a path-specific diagnostic but no fused score is assigned in this step.
- Test deterministic ordering for ties using rank and chunk ID.
- Test clear failure when `pg_search` is unavailable and no deterministic SQL-only fallback is being used by the test.

## Acceptance Criteria
- BM25 candidate retrieval is implemented through ParadeDB over sanitized chunks.
- Source allowlist, license, sensitivity, redaction, and version filters are applied before candidates leave SQL.
- BM25 scores are preserved for diagnostics but not compared directly with vector distances.
- CI has deterministic unit coverage without external services, plus integration coverage when `pg_search` is available.
- No raw unsanitized chunks are logged or returned.

## Suggested Commit Message
`feat: add bm25 candidate retrieval`
