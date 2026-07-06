# 4.2: Embedding Jobs And Vector Storage

## Goal
Embed changed sanitized chunks and store vectors in pgvector-backed tables with model, index-version, and sanitized-content-hash provenance.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Step 4.1 is complete.
- Phase 2 has created `embedding_models`, `embedding_jobs`, `index_versions`, and database migration plumbing.
- Phase 3 has created sanitized `chunks`, chunk tombstones or active flags, citations, redaction status, access labels, sensitivity class, and license policy status.
- Raw fetched source content remains outside Postgres and is never used by this step.

## Files To Create Or Modify
- `src/idp_brain/embeddings/jobs.py`
- `src/idp_brain/embeddings/storage.py`
- `src/idp_brain/db/models.py`
- `src/idp_brain/db/repositories/embeddings.py`
- `alembic/versions/<revision>_embedding_jobs_and_vectors.py`
- `tests/embeddings/test_embedding_jobs.py`
- `tests/embeddings/test_vector_storage.py`
- `tests/db/test_embedding_migration.py`

## Implementation Instructions
1. Add or complete SQLAlchemy models for `embedding_models`, `embedding_jobs`, and `embeddings` if Phase 2 only created placeholders.
2. Store one vector row per chunk, embedding model, and index version. Include `chunk_id`, `embedding_model_id`, `index_version_id`, `sanitized_content_hash`, `embedding`, `dimensions`, `created_at`, `updated_at`, and `is_active`.
3. Create embedding jobs only for chunks whose persisted text is sanitized, whose redaction status is allowed for embedding, whose license policy is allowed for retrieval, and whose active sanitized content hash differs from the stored embedding hash.
4. Never enqueue jobs from raw extractor output, raw local cache files, raw artifact text, or failed-redaction chunks.
5. Implement a `run_embedding_jobs_once()` worker function that:
   - claims pending jobs in bounded batches
   - loads only `chunks.sanitized_text` and sanitized metadata
   - calls the provider from Step 4.1
   - validates vector dimension
   - upserts the vector row with the current sanitized content hash
   - marks stale vectors inactive when chunk text, model ID, or index version changes
6. Add retry accounting and terminal failure state for provider errors. Store error class and sanitized diagnostic text only; do not store raw request bodies, raw response bodies, stack traces containing text, or API credentials.
7. Make job selection deterministic in tests by ordering by job creation time and chunk ID.
8. Keep job execution local-process based for the MVP. Do not introduce Celery, Temporal, or remote queues in this step.
9. Ensure tombstoned or deleted chunks cannot retain active embeddings in the active index version.
10. Add a small fixture corpus with sanitized chunks containing redaction markers to prove markers, not raw secrets, are embedded.

## Tests And Checks
- `uv run pytest tests/embeddings/test_embedding_jobs.py`
- `uv run pytest tests/embeddings/test_vector_storage.py`
- `uv run pytest tests/db/test_embedding_migration.py`
- `mise run db:migrate`
- Test that jobs are created only for sanitized, active, policy-allowed chunks.
- Test that a changed sanitized content hash creates a new job and deactivates the stale vector after success.
- Test that failed-redaction or license-disallowed chunks are not embedded.
- Test that mock-provider vectors are persisted with the expected dimension and model ID.
- Test that logs and job error records do not include raw chunk text or credentials.

## Acceptance Criteria
- Embeddings are derived only from sanitized chunk text and sanitized metadata.
- Vector rows are traceable to chunk ID, embedding model, index version, and sanitized content hash.
- CI can exercise the full job flow using the deterministic mock provider.
- Failed jobs are diagnosable without leaking source text.
- Stale and tombstoned chunks do not remain active in vector retrieval.

## Suggested Commit Message
`feat: store sanitized chunk embeddings`
