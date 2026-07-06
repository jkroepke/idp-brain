# 5.9: Evaluation Metrics

## Goal
Implement retrieval evaluation metrics and reporting for Recall@k, MRR, nDCG@10, hit rate, context precision, context recall, latency by retrieval stage, and abstention correctness.

## Prerequisites
- Step 5.8 has added `idp-brain eval run`.
- Retrieval events expose selected citation IDs, candidate ranks, retrieval stage timings, active index version, and redaction status.
- Evaluation cases include expected citation IDs or chunk IDs and expected abstention markers where applicable.
- `ARCHITECTURE.md` remains the source of truth for required retrieval metrics and optional answer-quality metrics.

## Files To Create Or Modify
- `src/idp_brain/evaluation/metrics.py`
- `src/idp_brain/evaluation/results.py`
- `src/idp_brain/evaluation/reporting.py`
- `src/idp_brain/retrieval/events.py`
- `config/evaluation.yaml`
- `tests/evaluation/test_metrics.py`
- `tests/evaluation/test_eval_reporting.py`

## Implementation Instructions
1. Add metric functions for:
   - `recall_at_k`
   - `mean_reciprocal_rank`
   - `ndcg_at_10`
   - `hit_rate`
   - `context_precision`
   - `context_recall`
   - `abstention_correctness`
2. Compute latency metrics by retrieval stage:
   - total retrieval latency
   - exact lookup latency
   - BM25 latency
   - vector latency
   - relationship traversal latency
   - fusion latency
   - reranking latency
   - evidence packaging latency
3. Report p50 and p95 latency for each stage over the eval run.
4. Calculate metrics separately by retrieval mode, query profile, category, active index version, embedding model ID, and reranker profile.
5. Keep generated answer-quality metrics optional. If Ragas or DeepEval are configured later, record faithfulness, answer relevancy, context precision, context recall, and hallucination rate separately from retrieval metrics.
6. Store selected citation IDs, expected citation IDs, rank positions, metric values, and redaction status. Do not store raw unsanitized chunk text, raw source files, full LLM prompts, vectors, SQL, or provider payloads.
7. Ensure metric functions are deterministic pure functions over sanitized IDs, ranks, labels, and timings so they can run in CI without external services.
8. Include per-category output for exact identifier lookup, source-code lookup, schema/API lookup, documentation lookup, release/version lookup, change-to-version lookup, version diff retrieval, conflict retrieval, stale source detection, source filters, token budget limits, redaction, PII filtering, license filtering, and retrieval mode comparisons.

## Tests And Checks
- `uv run pytest tests/evaluation/test_metrics.py tests/evaluation/test_eval_reporting.py`
- `uv run idp-brain eval run --cases tests/evaluation/fixtures/retrieval_cases.yaml --format json --diagnostic-only`
- `mise run ci`
- Tests must cover perfect match, partial match, no match, duplicate selections, empty expected sets, expected abstention, incorrect abstention, stage latency percentiles, category aggregation, mode aggregation, and deterministic ordering.

## Acceptance Criteria
- Eval reports include Recall@k, MRR, nDCG@10, hit rate, context precision, context recall, p50/p95 stage latency, and abstention correctness.
- Metrics are grouped by retrieval mode, query profile, category, index version, embedding model, and reranker profile.
- Metrics use citation or chunk identifiers and sanitized metadata only.
- Metric tests pass deterministically in local and CI environments.

## Suggested Commit Message
`feat: add retrieval evaluation metrics`
