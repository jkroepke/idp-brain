# 5.13: GitHub Actions Eval

## Goal
Add a GitHub Actions workflow for retrieval evaluation that runs the same `mise run eval` path as local development against an ephemeral database and sanitized fixture data.

## Prerequisites
- Step 5.8 has added `idp-brain eval run` and `mise run eval`.
- Step 5.9 has added retrieval quality metrics.
- Step 5.10 has added thresholds and CI gate behavior.
- Phase 1 CI and local PostgreSQL runtime are working.
- Phase 6 day-2 operations are not prerequisites for this workflow. The evaluation workflow must remain deterministic without starting the observability stack.
- `ARCHITECTURE.md` remains the source of truth for GitHub Actions, validation-only scheduled ingestion/eval, and durable database constraints.

## Files To Create Or Modify
- `.github/workflows/eval.yaml`
- `mise.toml`
- `config/evaluation.yaml`
- `tests/evaluation/fixtures/retrieval_cases.yaml`
- Optional: `.github/workflows/ci.yaml` only to call the eval workflow or document dependency ordering
- Optional: `README.md` only if workflow documentation is needed

## Implementation Instructions
1. Create `.github/workflows/eval.yaml`.
2. Trigger on:
   - pull requests that change retrieval, ingestion, evaluation, config, migrations, or workflow files.
   - pushes to the default branch.
   - manual `workflow_dispatch`.
   - a scheduled run only if it remains validation-only.
3. Install `mise`, restore practical caches, run `mise run install`, and start the same ephemeral PostgreSQL runtime used by local CI.
4. Run migrations and required extension/index smoke tests before eval:
   - `mise run db:migrate`
   - extension smoke test for `vector`, `pg_search`, and `pg_trgm`
   - fixture BM25 query and fixture vector query when available.
5. Seed only sanitized deterministic fixture data or run validation-only ingestion against fixture sources. Do not assume durable access to the server database.
6. Run `mise run eval`, which must delegate to `idp-brain eval run` with repository defaults.
7. Upload sanitized eval reports as workflow artifacts when useful. Reports must contain case IDs, metrics, selected citation IDs, expected citation IDs, thresholds, active index version, and failure summaries only.
8. Do not upload raw chunks, raw source files, local ingestion caches, database dumps containing source text, embeddings, SQL logs with sensitive literals, provider payloads, secrets, PII, or full prompts.
9. Ensure external embedding and reranking providers are disabled in the workflow unless explicitly allowed by repository policy. CI must use deterministic mock/local embedding and reranking fixtures by default.
10. Keep scheduled ingestion and scheduled eval validation-only until the repository defines export/import format, artifact encryption, retention, restore checks, and explicit promotion into an active `index_versions` record.
11. The workflow may fail on explicit thresholds and hard safety gates from `config/evaluation.yaml`; missing thresholds remain diagnostic-only.
12. Do not make Phase 5 CI depend on the Phase 6 telemetry backends, network access, or persistent volumes. Phase 6 adds its own integration validation after the local evaluation path is complete.

## Tests And Checks
- `yamllint .github/workflows/eval.yaml`
- `actionlint .github/workflows/eval.yaml`
- `mise run eval`
- `mise run ci`
- If `act` is available: `act pull_request -W .github/workflows/eval.yaml`
- Passing condition: workflow syntax is valid, local eval passes or reports diagnostic-only metrics as configured, and no external provider credentials are required.

## Acceptance Criteria
- GitHub Actions runs retrieval evals against an ephemeral local database and sanitized deterministic fixtures.
- The workflow uses the same `mise run eval` path as local development.
- Eval artifacts are sanitized and do not contain raw chunks, secrets, PII, vectors, provider payloads, SQL logs with sensitive literals, or local cache files.
- Scheduled eval and ingestion remain validation-only until promotion/export/import rules exist.
- Explicit thresholds and hard safety gates can fail CI; missing thresholds remain diagnostic-only.
- The workflow succeeds independently of the Phase 6 day-2 operations stack.

## Suggested Commit Message
`ci: add retrieval evaluation workflow`
