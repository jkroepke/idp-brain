# 2.6: Index Versions And Embedding Jobs

## Goal
Add data models for index versions, embedding models, embeddings, and embedding jobs so later ingestion can build inactive indexes, evaluate them, and activate or roll back safely.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 2.5 is complete.
- Sanitized chunks and policy metadata exist.
- This step creates schema only; embedding generation, BM25 creation, HNSW tuning, and retrieval run in later phases.

## Files To Create Or Modify
- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/models/indexing.py`
- `src/idp_brain/models/embedding.py`
- `src/idp_brain/models/__init__.py`
- `migrations/versions/0005_index_versions_embedding_jobs.py`
- `tests/test_index_embedding_models.py`

## Implementation Instructions
1. Add `pgvector` Python integration only if it is needed to declare vector columns in SQLAlchemy. Keep provider SDKs out of this step.
2. Add `embedding_models` with provider name, model name, provider model ID, dimensions, modality or corpus scope, distance metric, tokenizer or profile name, config hash, deterministic flag, external calls allowed flag, promotion status, created timestamp, and retired timestamp.
3. Seed or fixture a deterministic local/mock embedding model for CI. Remote profiles such as OpenAI, Jina, BAAI, Cohere, LiteLLM, vLLM, BentoML, or KServe must remain inactive unless explicitly enabled by configuration in a later step.
4. Add `index_versions` with index version ID, name, index kind, corpus scope, source scope, embedding model ID when applicable, BM25 profile, vector profile, exact index profile, relationship profile, chunking profile, reranker profile, config hash, status, built-from ingestion run ID, activated timestamp, retired timestamp, and failure metadata.
5. Add or tighten the foreign key from `retrieval_events.active_index_version_id` to `index_versions` once both tables exist, while keeping the field nullable for events recorded before activation.
6. Add `embeddings` with chunk ID, embedding model ID, index version ID, sanitized input hash, vector value, dimensions, distance metric, created timestamp, and uniqueness over chunk/model/index/input hash.
7. Add `embedding_jobs` with job ID, chunk ID, embedding model ID, index version ID, sanitized input hash, status, attempt count, next retry timestamp, provider request hash, provider response metadata JSON, sanitized error code/message, and timestamps.
8. Do not store input text, raw source content, unsanitized chunks, provider prompts, API keys, provider raw responses, or full sensitive error payloads in embedding records or jobs.
9. Model index activation as an atomic status transition for later code. Rollback means activating a previous `index_versions` record, not mutating rows in place.
10. Keep embedding fine-tuning out of MVP. `finetuning_runs` may remain absent or disabled unless the existing architecture step already created it as a future-only table.

## Tests And Checks
- `mise run up`
- `mise run db:migrate`
- `uv run pytest tests/test_index_embedding_models.py`
- `mise run lint`
- `mise run test`
- Include tests that insert a deterministic mock embedding model, create an inactive index version, enqueue an embedding job from a sanitized hash, store a vector for a sanitized chunk, verify the retrieval event index-version reference can be constrained when present, and assert no raw text columns exist.
- Passing condition: index and embedding state is fully reproducible from migrations and requires no external model provider in CI.

## Acceptance Criteria
- Index versions, embedding models, embeddings, and embedding jobs are canonical and migration-managed.
- Active and inactive indexes can be represented for blue/green promotion and rollback.
- CI has a deterministic local/mock embedding path.
- Remote model serving and embedding fine-tuning remain out of MVP.
- Embedding jobs and vectors reference sanitized chunks only.

## Suggested Commit Message
`feat: add index version and embedding job models`
