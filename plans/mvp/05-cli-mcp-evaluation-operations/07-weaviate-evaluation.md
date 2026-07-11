# 5.7: Adapt Evaluation To Weaviate

## Goal

Reuse behavioral evaluation assets while removing assertions tied to PostgreSQL, ParadeDB, pgvector, RRF, and the old evidence-bundle implementation.

## Instructions

1. Keep evaluation cases that describe user-visible retrieval intent and expected evidence IDs.
2. Run profiles through the same thin Weaviate adapter used by the CLI.
3. Compare:
   - BM25-only
   - vector-only
   - hybrid
   - named-vector choices
   - optional Weaviate-supported reranking
4. Measure Recall@k, MRR, nDCG, hit rate, citation completeness, redaction safety, and latency.
5. Do not compare raw scores across retrieval engines.
6. Delete tests whose only purpose is validating SQL shape, ORM filtering, migration state, RRF arithmetic, or application-owned reranker plumbing.
7. Keep deterministic vectors or a pinned local vectorizer for CI.
8. Do not require paid provider credentials.

## Checks

- evaluation is reproducible from a clean collection
- expected evidence IDs and citations pass configured thresholds
- no PostgreSQL service is used by the evaluation path
- no legacy score parity gate exists
- `mise run eval`
- `mise run ci`

## Acceptance Criteria

Evaluation protects retrieval quality and safety without preserving legacy implementation details.
