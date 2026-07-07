# 4.10: Reciprocal Rank Fusion

## Goal
Merge exact, BM25, vector, relationship, and future memory candidates with reciprocal-rank fusion while preserving path-specific diagnostics.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Steps 4.5, 4.6, and 4.7 return candidate lists with stable ranks.
- Step 4.8 defines fusion method, weights, and bounded relationship traversal settings in query profiles.
- Step 4.9 ensures candidates and relationship edges have already passed trusted filters.
- BM25 scores and vector distances remain path-specific diagnostics only.

## Files To Create Or Modify
- `src/idp_brain/retrieval/fusion.py`
- `src/idp_brain/retrieval/models.py`
- `src/idp_brain/retrieval/service.py`
- `tests/retrieval/test_reciprocal_rank_fusion.py`
- `tests/retrieval/test_hybrid_retrieval_service.py`

## Implementation Instructions
1. Implement `reciprocal_rank_fusion(candidate_lists, weights, rank_constant)` using:
   ```text
   fused_score(chunk_id) += weight(path) / (rank_constant + rank(path, chunk_id))
   ```
2. Use `rank_constant = 60` as the default unless `config/retrieval.yaml` overrides it.
3. Deduplicate candidates by `chunk_id`. Preserve each contributing retrieval path, original rank, BM25 score, vector distance, exact matched fields, relationship path metadata, and candidate source profile.
4. Add profile weights for `exact`, `bm25`, `vector`, `relationship`, and `memory`, with memory defaulting to disabled or zero weight until the memory retrieval path is implemented.
5. Treat lower vector distance as better only when computing the vector path rank before fusion. Do not compare raw vector distance to BM25 score or exact match confidence.
6. Treat higher BM25 score as better only when computing the BM25 path rank before fusion. Do not normalize BM25 score into vector distance space.
7. Make tie-breaking deterministic: fused score descending, best exact rank, best BM25 rank, best vector rank, authority rank, freshness, chunk ID.
8. Include authority and freshness as configured rerank/final-order signals only after candidate fusion, not as a reason to bypass corpus eligibility filters or evidence requirements.
9. Add a bounded relationship candidate expansion inside `HybridRetrievalService` when the active profile enables it. It must start from filtered seed candidates, traverse only normalized PostgreSQL relationship rows from Step 4.9, honor profile depth/fanout/type/direction/candidate limits, and return citation-backed entity or chunk candidate IDs with relationship path metadata.
10. Treat relationship candidates as their own ranked path before fusion. They must not replace exact, BM25, or vector evidence, and they must not be generated from ineligible or uncited relationship endpoints.
11. Add a `HybridRetrievalService` orchestration method that obtains filtered candidates from exact, BM25, vector, and enabled bounded relationship traversal, fuses them, and passes the fused list to the reranker step when configured.
12. Keep final evidence snippets out of this step. Fusion returns ranked candidate IDs and diagnostics for Step 4.11 and Step 4.12.
13. Make the fusion function pure and deterministic so unit tests can cover ranking without a database.

## Tests And Checks
- `uv run pytest tests/retrieval/test_reciprocal_rank_fusion.py`
- `uv run pytest tests/retrieval/test_hybrid_retrieval_service.py`
- Test single-path, multi-path, duplicate-candidate, missing-path, weighted-path, and tie-break cases.
- Test that BM25 scores and vector distances are not directly added, subtracted, normalized together, or compared to each other.
- Test that filtered-out candidates are not accepted by the hybrid service.
- Test that relationship candidates are bounded by profile depth, fanout, type, direction, and candidate limits before fusion.
- Test that lineage, dependency, conflict, and impact relationship candidates retain path metadata and citation-backed chunk or entity IDs.
- Test that exact-only, BM25-only, vector-only, relationship-only, and fused hybrid rankings are observable for evaluation.
- Test deterministic output order across repeated runs.

## Acceptance Criteria
- Hybrid retrieval uses reciprocal-rank fusion by default.
- Candidate diagnostics preserve path-specific ranks and scores without mixing score domains.
- Relationship expansion is optional, filtered, bounded, deterministic, and represented as a distinct fusion path.
- Fusion is deterministic and covered by database-free unit tests.
- The hybrid service can report exact-only, BM25-only, vector-only, relationship-only, and fused candidate lists for evaluation.
- Fused candidates remain sanitized IDs and metadata until evidence packaging.

## Suggested Commit Message
`feat: add reciprocal rank fusion`
