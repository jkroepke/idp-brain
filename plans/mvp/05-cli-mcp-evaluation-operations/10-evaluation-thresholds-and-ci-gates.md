# 5.10: Evaluation Thresholds And CI Gates

## Goal
Define release-blocking retrieval and safety thresholds in `config/evaluation.yaml` and enforce them in eval and CI only when explicitly configured.

## Prerequisites
- Step 5.8 has added `idp-brain eval run`.
- Step 5.9 has added retrieval metrics and reporting.
- Security, redaction, citation, ACL, lineage, freshness, and conflict fixtures exist.
- `ARCHITECTURE.md` remains the source of truth for release gates and the rule that thresholds must exist before gates block releases.

## Files To Create Or Modify
- `config/evaluation.yaml`
- `src/idp_brain/evaluation/thresholds.py`
- `src/idp_brain/evaluation/runner.py`
- `src/idp_brain/evaluation/reporting.py`
- `tests/evaluation/test_thresholds.py`
- `tests/evaluation/test_eval_gates.py`
- `mise.toml`

## Implementation Instructions
1. Add threshold configuration under `config/evaluation.yaml` for:
   - minimum Recall@k by category and retrieval mode.
   - minimum MRR by category and retrieval mode.
   - minimum nDCG@10 by category and retrieval mode.
   - minimum hit rate by category and retrieval mode.
   - minimum context precision and context recall when context metrics are configured.
   - maximum p95 total retrieval latency.
   - maximum p95 latency by exact, BM25, vector, relationship, fusion, reranking, and packaging stage.
   - required abstention correctness for missing-evidence cases.
2. Add hard safety gates for:
   - no secret leakage into embeddings.
   - no disallowed PII leakage into embeddings, logs, eval data, or LLM context.
   - no uncited answer context.
   - no retrieval regression on fixture questions.
   - no false first-version claim when lineage is unknown.
   - no stale source selected when a fresher matching source exists.
   - no ignored source conflict when conflicting evidence is present.
   - no tuned embedding promotion without held-out metric improvement.
3. Implement threshold evaluation that returns pass, fail, or diagnostic-only for every metric and gate.
4. If a threshold is missing, report the metric as diagnostic-only and do not fail the command or CI on that metric.
5. `idp-brain eval run --fail-on-threshold` must exit non-zero only when an explicitly configured threshold or hard safety gate fails.
6. Keep scheduled ingestion and scheduled evaluation validation-only. They may report failures and upload sanitized artifacts, but must not promote index versions, publish tuned embeddings, or assume durable access to a server database.
7. Store threshold decisions in `eval_results` with sanitized case IDs, metric values, threshold values, gate names, active index version, and failure reasons.
8. Do not store raw chunks, raw source files, full prompts, secrets, PII, vectors, SQL, or provider payloads in threshold reports.

## Tests And Checks
- `uv run pytest tests/evaluation/test_thresholds.py tests/evaluation/test_eval_gates.py`
- `uv run idp-brain eval run --cases tests/evaluation/fixtures/retrieval_cases.yaml --fail-on-threshold`
- `mise run eval`
- `mise run ci`
- Tests must cover missing thresholds as diagnostic-only, passing thresholds, failing thresholds, hard safety gate failure, exit codes, sanitized failure output, and validation-only scheduled behavior.

## Acceptance Criteria
- `config/evaluation.yaml` can express retrieval metric thresholds, latency thresholds, and hard safety gates.
- Eval gates fail only when thresholds or hard gates are explicitly configured and violated.
- Safety gates cover redaction, PII, citations, regression, lineage, freshness, conflicts, and tuned embedding promotion.
- CI and scheduled jobs remain validation-only until explicit promotion/export/import rules exist.

## Suggested Commit Message
`feat: add eval thresholds and gates`
