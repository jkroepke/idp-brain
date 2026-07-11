# 6.8: Shadow Evaluation And Relevance Parity

## Goal

Compare the Weaviate path with the established PostgreSQL, ParadeDB, and pgvector baseline and prove that the migration preserves or improves retrieval quality and safety before cutover.

## Prerequisites

- Steps 6.5 through 6.7 provide a complete inactive Weaviate retrieval path.
- Phase 5 evaluation cases and thresholds are available.
- The old retriever is frozen and reproducible.

## Files To Create Or Modify

- `src/idp_brain/evaluation/shadow.py`
- `src/idp_brain/evaluation/runner.py`
- `config/evaluation.yaml`
- `mise.toml`
- migration evaluation reports
- CI workflow for migration validation

## Implementation Instructions

1. Add a migration-only shadow evaluator that runs the same normalized request against both backends.
2. Do not require identical scores or ordering algorithms. Compare behavior through evidence IDs, citations, and quality metrics.
3. Measure at least:
   - Recall@k.
   - MRR.
   - nDCG@10.
   - hit rate.
   - p50 and p95 latency.
   - abstention correctness.
   - citation completeness.
   - policy-filter correctness.
4. Compare categories:
   - exact identifiers.
   - documentation.
   - source code.
   - schemas and APIs.
   - releases and version lineage.
   - conflicts and relationships.
   - source and policy filters.
   - stale source handling.
   - token-budget behavior.
5. Run Weaviate BM25-only, vector-only, and hybrid profiles so regressions can be attributed to lexical, semantic, or fusion configuration.
6. Tune query profile alpha, lexical properties, target vectors, result counts, and reranker configuration through configuration changes only.
7. Record safe result IDs, ranks, citation IDs, score metadata, and exclusion reasons. Do not persist raw queries or source content in migration reports unless the fixture repository already contains approved sanitized test data.
8. Define cutover thresholds before the run is release-blocking.
9. Treat any secret, PII, license, visibility, sensitivity, redaction, version, or citation regression as blocking even if relevance improves.
10. Add `mise run migration:shadow-eval`.
11. Keep the report as a build artifact or ignored local output, not a new runtime database.

## Tests And Checks

- Run the complete held-out retrieval suite against both backends.
- Verify deterministic results for the same collection generation and configuration.
- Verify every safety category is a hard gate.
- Review the largest relevance gains and regressions.
- Re-run after configuration tuning.
- `mise run ci`

## Acceptance Criteria

- Weaviate meets the configured held-out quality thresholds.
- No safety, eligibility, citation, freshness, or lineage gate regresses.
- Performance is measured and acceptable for the MVP.
- Remaining differences are understood and documented.
- The old backend is no longer required as a quality fallback.

## Suggested Commit Message

`test: validate weaviate retrieval migration`
