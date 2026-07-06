# 5.8: Eval Run Command

## Goal
Add `idp-brain eval run` as the local and CI command for retrieval regression evaluation, measuring retrieval quality separately from generated answer quality.

## Prerequisites
- Phase 4 retrieval service can run exact-only, BM25-only, vector-only, and fused hybrid retrieval paths.
- Steps 5.2 and 5.3 have added query and diagnostic command paths.
- Sanitized eval fixtures and expected citation IDs can be loaded from repository-controlled files.
- `config/evaluation.yaml` exists or is created in this step.
- `ARCHITECTURE.md` remains the source of truth for evaluation metrics, categories, safety gates, and diagnostic behavior before thresholds exist.

## Files To Create Or Modify
- `src/idp_brain/cli.py`
- `src/idp_brain/cli/eval.py`
- `src/idp_brain/evaluation/runner.py`
- `src/idp_brain/evaluation/cases.py`
- `src/idp_brain/evaluation/results.py`
- `src/idp_brain/evaluation/reporting.py`
- `config/evaluation.yaml`
- `tests/evaluation/fixtures/retrieval_cases.yaml`
- `tests/cli/test_eval_run_command.py`
- `tests/evaluation/test_eval_runner.py`
- `mise.toml`

## Implementation Instructions
1. Register a Typer sub-application at `idp-brain eval`.
2. Add `idp-brain eval run` with options:
   - `--cases PATH`, defaulting to the path configured in `config/evaluation.yaml`.
   - `--profile TEXT`, repeatable retrieval profile filter.
   - `--category TEXT`, repeatable evaluation category filter.
   - `--mode exact-only|bm25-only|vector-only|hybrid`, repeatable or defaulting to all configured modes.
   - `--output PATH`, optional JSON report path.
   - `--format table|json|junit`, defaulting to `table`.
   - `--fail-on-threshold/--diagnostic-only`, defaulting according to `config/evaluation.yaml`.
   - `--limit INTEGER`, optional bounded case count for smoke runs.
3. Load human-authored golden cases from YAML or JSON. Each case must include a stable case ID, query, category, expected citation IDs or chunk IDs, allowed source/version filters, optional token budget, and expected abstention behavior.
4. Synthetic query-context pairs may be loaded only when they are generated from approved sanitized chunks and marked as synthetic. They must never be treated as authoritative evidence.
5. Run retrieval through the shared retrieval service. Do not query SQL, pgvector, ParadeDB, or rerankers directly from the eval runner.
6. Evaluate exact-only, BM25-only, vector-only, and fused hybrid retrieval separately so regressions identify the failing retrieval path.
7. Store `eval_results` with sanitized queries, case IDs, expected citation IDs, selected citation IDs, metrics, active index version, embedding model ID, reranker profile, redaction status, timestamps, and diagnostic-only or gate status.
8. Provide deterministic CI fallback through fixture indexes, mock embeddings, and mock reranking. No external model, network, or durable server database is required for command tests.
9. Add or update `mise run eval` so it delegates to `idp-brain eval run` with repository defaults.
10. Until `config/evaluation.yaml` defines explicit thresholds, evaluation failures are diagnostic and must not block releases.

## Tests And Checks
- `uv run idp-brain eval --help`
- `uv run idp-brain eval run --help`
- `uv run idp-brain eval run --cases tests/evaluation/fixtures/retrieval_cases.yaml --format json --diagnostic-only`
- `uv run pytest tests/cli/test_eval_run_command.py tests/evaluation/test_eval_runner.py`
- `mise run eval`
- `mise run ci`
- Tests must cover case loading, category filtering, retrieval mode comparison, expected citation matching, expected abstention, JSON and table output, result persistence, diagnostic-only default without thresholds, and deterministic mock provider fallback.

## Acceptance Criteria
- `idp-brain eval run` evaluates retrieval cases and reports metrics for exact-only, BM25-only, vector-only, and hybrid retrieval.
- Evaluation data and results contain sanitized evidence identifiers and metadata only.
- CI can run evals deterministically without external services or a durable server database.
- Thresholds control release-blocking behavior only after they are explicitly configured.

## Suggested Commit Message
`feat: add retrieval eval run command`
