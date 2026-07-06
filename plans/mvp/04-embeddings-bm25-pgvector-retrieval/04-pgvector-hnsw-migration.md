# 4.4: pgvector HNSW Migration

## Goal
Add migration-managed pgvector HNSW indexes for broad dense retrieval while preserving exact vector search for small filtered subsets and correctness tests.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Step 4.2 has created or completed the `embeddings` table.
- Phase 1 extension smoke tests can create `vector`.
- Embedding dimensions are fixed per active embedding model or stored in a schema pattern that supports model-specific indexes.
- `config/retrieval.yaml` will own HNSW query tuning rather than hardcoded constants.

## Files To Create Or Modify
- `alembic/versions/<revision>_embeddings_hnsw_index.py`
- `src/idp_brain/db/migration_checks.py`
- `tests/db/test_pgvector_hnsw_migration.py`
- `tests/retrieval/test_vector_extension_smoke.py`

## Implementation Instructions
1. In the Alembic upgrade, verify or rely on the Phase 1 migration that runs `CREATE EXTENSION IF NOT EXISTS vector`.
2. Create an HNSW cosine index for the active embedding vector column:
   ```sql
   CREATE INDEX embeddings_hnsw_cosine_idx
   ON embeddings
   USING hnsw (embedding vector_cosine_ops);
   ```
3. If the implemented schema stores different dimensions or model families in separate tables or generated columns, create explicit model/profile-specific HNSW indexes and document the mapping in the migration comments.
4. Keep exact vector search available by leaving the base `embedding <=> :query_embedding` ordering valid without forcing ANN-only behavior.
5. Add B-tree indexes for `embedding_model_id`, `index_version_id`, `chunk_id`, and `is_active` if they do not already exist, because vector retrieval must join through filtered chunk scopes before ranking.
6. Add a downgrade that drops HNSW and supporting indexes created by this step.
7. Do not store query embeddings, source text, or provider payloads in migration diagnostics.
8. Configure runtime HNSW knobs such as `hnsw.ef_search` through `config/retrieval.yaml` in a later step; this migration should create indexes, not choose query policy.
9. Add a small smoke fixture that inserts deterministic mock vectors and verifies cosine distance ordering with `<=>`.

## Tests And Checks
- `mise run db:migrate`
- `uv run pytest tests/db/test_pgvector_hnsw_migration.py`
- `uv run pytest tests/retrieval/test_vector_extension_smoke.py -m requires_pgvector`
- Verify that `embeddings_hnsw_cosine_idx` exists after migration and is absent after downgrade.
- Verify that `ORDER BY embedding <=> :query_embedding LIMIT 5` works against fixture vectors.
- Verify that vector rows join to active, sanitized chunks before any retrieval result is returned.

## Acceptance Criteria
- pgvector HNSW cosine indexes are reproducible through Alembic.
- Exact vector ordering remains available for highly selective filtered subsets and tests.
- Dense retrieval has supporting indexes for model, index version, and active-state filtering.
- The migration contains no source-content logging, embedding payload dumps, or raw text references.
- HNSW query tuning remains configuration-owned.

## Suggested Commit Message
`feat: add pgvector hnsw index migration`
