# 4.8: Query Profiles

## Goal
Define retrieval query profiles in configuration and typed code for documentation QA, code QA, API symbol lookup, release/change search, conflict search, and bounded relationship expansion.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 2 configuration loading exists.
- Steps 4.5, 4.6, and 4.7 have candidate retrievers that can accept profile settings.
- `config/models.yaml` defines embedding and reranker profile IDs referenced by retrieval profiles.
- Normalized PostgreSQL relationship records exist for lineage, dependency, conflict, and impact edges, or the active schema exposes equivalent normalized relationship tables.
- The architecture remains the authority for profile names and responsibilities.

## Files To Create Or Modify
- `config/retrieval.yaml`
- `src/idp_brain/config/retrieval.py`
- `src/idp_brain/retrieval/profiles.py`
- `tests/config/test_retrieval_config.py`
- `tests/retrieval/test_query_profiles.py`

## Implementation Instructions
1. Add a typed `RetrievalProfile` model with profile ID, exact lookup fields, BM25 fields, vector settings, embedding profile ID, relationship traversal settings, candidate counts, fusion method, fusion weights, reranker profile ID, authority weighting, freshness weighting, token budget, and diagnostic settings.
2. Add the required profiles to `config/retrieval.yaml`:
   - `docs_qa`
   - `code_qa`
   - `api_symbol_lookup`
   - `release_change_search`
   - `conflict_search`
3. Configure `docs_qa` for narrative documentation, examples, tables, generated API docs, headings, release notes, BM25 candidates, and dense candidates over documentation embeddings.
4. Configure `code_qa` for exact symbol and path lookup first, then AST/code chunks, imports, signatures, code embeddings, and documentation backfill.
5. Configure `api_symbol_lookup` for exact names, symbols, fields, endpoint paths, schema keys, flags, methods, functions, error strings, and signature text before broader semantic retrieval.
6. Configure `release_change_search` for version lineage, changelog entries, release notes, commits, tags, diffs, first-seen version, and last-seen version metadata.
7. Configure `conflict_search` for normalized claims, `claim_conflicts`, competing citations, and profile behavior that keeps both sides of a relevant conflict when allowed by filters.
8. Configure bounded relationship traversal per profile with allowed relationship types, maximum depth, maximum fanout per seed, maximum relationship candidates, direction, cycle handling, and whether traversal starts from exact, BM25, vector, or fused seed candidates.
9. Keep traversal disabled by default for profiles that do not need it. Enable only bounded lineage traversal for `release_change_search`, dependency or impact traversal for code/API profiles where configured, and conflict-edge traversal for `conflict_search`.
10. Set default candidate limits within the architecture range of 50 to 200 for BM25 and vector retrieval, with smaller exact lookup limits where appropriate, and separate relationship limits that cannot expand the final candidate pool beyond configured bounds.
11. Set default fusion method to `reciprocal_rank_fusion`; do not configure direct BM25-score-to-vector-distance comparison.
12. Require every profile to declare the filter dimensions it honors: source allowlist, visibility, sensitivity class, license policy status, version or release scope, and active index version.
13. Validate that every referenced embedding model, vector index, BM25 field, relationship type, reranker profile, and fusion method exists or has a clear placeholder for a later step.
14. Keep profile selection generic. Do not hardcode Crossplane, Kubernetes, Flux, or any other product-specific catalog in profile logic.

## Tests And Checks
- `uv run pytest tests/config/test_retrieval_config.py`
- `uv run pytest tests/retrieval/test_query_profiles.py`
- `uv run python -m idp_brain.config.validate config/retrieval.yaml`
- Test that all five required profiles load and validate.
- Test that candidate counts are bounded and deterministic.
- Test that relationship traversal settings reject unbounded depth, fanout, candidate counts, unknown relationship types, and traversal without required filters.
- Test that direct BM25/vector score comparison is rejected by config validation.
- Test that each profile declares required filters and active index-version behavior.
- Test that missing model, reranker, or field references fail with actionable errors.

## Acceptance Criteria
- `config/retrieval.yaml` contains the five architecture-required query profiles.
- Candidate retrievers receive behavior from typed profile configuration rather than hardcoded constants.
- Filter dimensions are mandatory for every profile.
- Relationship traversal is profile-driven, bounded by configuration, and disabled unless a profile explicitly enables specific normalized PostgreSQL relationship types.
- The default fusion method is reciprocal-rank fusion or another explicitly calibrated method, never raw score comparison.
- Profile loading works deterministically in local development and CI.

## Suggested Commit Message
`feat: add retrieval query profiles`
