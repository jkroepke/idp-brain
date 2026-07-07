# 2.2: Example Config Files

## Goal
Add safe, versioned example configuration files for the complete MVP configuration surface so local development and CI have deterministic defaults.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 2.1 is complete.
- The config loader rejects unknown versions and invalid cross-file references.
- No real external credentials, external model calls, or durable ingestion output are required.

## Files To Create Or Modify
- `config/sources.yaml`
- `config/extractors.yaml`
- `config/models.yaml`
- `config/retrieval.yaml`
- `config/evaluation.yaml`
- `config/security.yaml`
- `config/corpus.yaml`
- `config/memory.yaml`
- `tests/test_example_configs.py`

## Implementation Instructions
1. Create all eight required config files with `config_version: 1`.
2. Keep examples generic and local-first. Use a disabled or local `documentation_file`/`local_directory` example rather than a live remote repository that CI must fetch.
3. In `sources.yaml`, include source ID, source type, local path or URL field, tracked refs or explicit version, version strategy, include/exclude paths, extractor profile, source priority, visibility label, corpus eligibility labels, sensitivity class, license policy, and refresh cadence.
4. In `extractors.yaml`, define separate profiles for Markdown/HTML docs, source code, JSON/YAML/TOML/schema files, OpenAPI, rich documents, and repository digest fallback. Mark Docling, Tika, Unstructured, Semgrep, Presidio, ScanCode, and ORT as optional profiles unless their dependencies are already installed.
5. In `models.yaml`, define active deterministic local/mock embedding and reranker profiles for CI. Include OpenAI, Jina, BAAI, Cohere, LiteLLM, vLLM, BentoML, or KServe only as disabled examples with no secrets and no active remote model serving.
6. In `retrieval.yaml`, define query profiles for `docs_qa`, `code_qa`, `api_symbol_lookup`, `release_change_search`, and `conflict_search`. Each profile must name exact lookup fields, BM25 fields, vector index, embedding model, candidate counts, fusion method, reranker, freshness weighting, authority weighting, and token budget.
7. In `evaluation.yaml`, configure local deterministic fixtures and diagnostic thresholds. Do not make thresholds release-blocking until fixture quality and gate policy are explicitly defined.
8. In `security.yaml`, define source allowlist defaults, redaction markers, secret-like value rules, PII profile placeholders, prompt-injection handling, and a rule that source text is data, never instruction.
9. In `corpus.yaml`, define visibility labels, global corpus eligibility defaults, source filters, sensitivity labels, license policy labels, and a default-deny fallback for unknown labels.
10. In `memory.yaml`, define `session`, `project`, `user`, and `system` scopes, memory item types, retention defaults, promotion requirements, and retrieval influence limits. Do not add memory UI or automatic memory writes.
11. Add tests that load the example config directory through `load_config_dir()` and assert active model/reranker providers are deterministic local/mock providers in CI.
12. Keep comments concise and avoid putting secrets, tokens, raw source chunks, or real private URLs in examples.

## Tests And Checks
- `uv run pytest tests/test_example_configs.py`
- `uv run pytest tests/test_config_loader.py`
- `mise run lint`
- `mise run test`
- If `yamllint` is configured: `yamllint config`
- Passing condition: every example config file validates locally, all cross-file references resolve, and CI can run without external APIs or remote model servers.

## Acceptance Criteria
- The repository has safe example files for every required configuration area.
- The examples cover sources, extractors, models, retrieval, evaluation, security, corpus, and memory without requiring code changes for a new source.
- Active defaults use deterministic local/mock embedding and reranking.
- source allowlist, license, sensitivity, and redaction labels are present for later pre-subquery filtering.
- memory UX, embedding fine-tuning, production HA, and remote model serving remain out of MVP.

## Suggested Commit Message
`docs: add versioned example configuration`
