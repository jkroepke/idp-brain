# 2.1: Config Loader Models

## Goal
Add typed Pydantic models and loader functions for the versioned configuration files that drive sources, extractors, models, retrieval, evaluation, security, corpus, and memory policy.

## Prerequisites
- Phase 1.1 through Phase 1.8 are complete.
- `ARCHITECTURE.md` and `plans/mvp/README.md` remain the source of truth.
- No ingestion, database persistence, retrieval, or external model calls are implemented in this step.

## Files To Create Or Modify
- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/config/__init__.py`
- `src/idp_brain/config/models.py`
- `src/idp_brain/config/loader.py`
- `src/idp_brain/config/errors.py`
- `tests/test_config_loader.py`

## Implementation Instructions
1. Add a YAML parser dependency such as `PyYAML` unless an equivalent dependency already exists.
2. Create Pydantic models with `extra="forbid"` for these versioned files: `sources.yaml`, `extractors.yaml`, `models.yaml`, `retrieval.yaml`, `evaluation.yaml`, `security.yaml`, `corpus.yaml`, and `memory.yaml`.
3. Require each top-level config model to include `config_version: 1` and a stable schema name or kind so future migrations can reject unknown versions deterministically.
4. Model `config/sources.yaml` with source IDs, source type, repository or artifact URL, tracked refs, version strategy, include/exclude paths, extractor profile, source priority, visibility label, corpus eligibility labels, sensitivity class, license policy, and refresh cadence.
5. Include source type values for `git_repository`, `git_repository_digest`, `release_artifact`, `documentation_site`, `documentation_file`, `openapi_spec`, `schema_bundle`, and `local_directory`.
6. Model extractor profiles for code, docs, schemas, API specs, repository digest fallback, security scanners, and configured validator commands without hardcoding any tool-specific catalog.
7. Model `models.yaml` with embedding, reranker, generator, provider routing, budgets, and deterministic local/mock providers. External model profiles must be disabled unless settings explicitly allow external calls.
8. Model `retrieval.yaml` query profiles for `docs_qa`, `code_qa`, `api_symbol_lookup`, `release_change_search`, and `conflict_search`, including exact fields, BM25 fields, vector index, embedding model, candidate counts, fusion method, reranker, freshness weighting, authority weighting, and token budget.
9. Model `evaluation.yaml` as diagnostic by default until thresholds are explicitly configured. Keep embedding fine-tuning settings present only as disabled future configuration.
10. Model `security.yaml`, `corpus.yaml`, and `memory.yaml` for redaction rules, prompt-injection handling, source allowlists, corpus eligibility labels, memory scopes, retention, and promotion rules. Memory UX is out of MVP; this step only validates configuration.
11. Implement `load_config_dir(config_dir: Path) -> ConfigBundle` and per-file loader helpers that validate all required files, report file paths in errors, and perform cross-file checks for referenced extractor, model, reranker, visibility, sensitivity, and license labels.
12. Ensure loading configuration never fetches repositories, opens external URLs, calls model providers, reads source content, persists data, logs raw source text, or starts database connections.

## Tests And Checks
- `uv run pytest tests/test_config_loader.py`
- `mise run lint`
- `mise run test`
- Include tests for valid minimal config, missing files, invalid `config_version`, unknown keys, duplicate source IDs, unknown extractor profile references, unknown model references, and disabled external model profiles.
- Passing condition: config loading is deterministic, pure local file validation and makes no network, database, embedding, reranking, or ingestion calls.

## Acceptance Criteria
- All required MVP config files have typed Pydantic models.
- The loader returns one validated `ConfigBundle` for later CLI, ingestion, retrieval, and evaluation code.
- Cross-file references fail fast with actionable errors.
- Deterministic local/mock embedding and reranking profiles are representable for CI.
- Raw unsanitized chunks are never loaded, persisted, embedded, logged, returned, or sent to any provider in this step.

## Suggested Commit Message
`feat: add typed configuration loader`
