# 6.5: Batch Import, Vectorization, And Index Build

## Goal

Import mapped objects into an inactive Weaviate collection generation and let Weaviate build lexical and vector indexes with bounded retries and measurable completeness.

## Prerequisites

- Step 6.4 produces validated sanitized object streams and a migration manifest.
- Collection bootstrap succeeds for a new inactive generation.
- Vectorizer and reranker provider profiles are configured.

## Files To Create Or Modify

- `src/idp_brain/migration/import_weaviate.py`
- `src/idp_brain/store/batch.py`
- `config/models.yaml`
- `config/weaviate.yaml`
- migration tasks
- import and vectorization tests

## Implementation Instructions

1. Create the target collection generation before import. It must not be active for normal retrieval.
2. Use the Weaviate client's recommended dynamic or fixed-size batch API with bounded concurrency, timeout, and retry settings.
3. Import objects using deterministic UUIDs so retries are idempotent.
4. Record failed object IDs and safe error classes. Do not log object content or provider payloads.
5. Re-vectorize sanitized content through the configured Weaviate vectorizer by default. Do not preserve pgvector embeddings merely to protect sunk work.
6. Allow bring-your-own vectors only for:
   - deterministic CI fixtures.
   - an explicitly approved offline profile.
   - a measured migration optimization with matching model identity and dimensions.
7. Route content to the correct named vector profile: docs, code, schema, or memory.
8. Exclude fields such as IDs, URLs, policy labels, and checksums from vectorization unless evaluation proves they help.
9. Configure BM25F-searchable properties, tokenization, and property weights through collection configuration.
10. Wait for batch completion and verify:
    - object counts by collection.
    - vector availability for required objects.
    - no failed batches remain.
    - lexical, vector, filtered, and hybrid fixture queries succeed.
11. Persist a safe import result containing target generation, counts, failures, duration, vectorizer identity, and schema manifest hash.
12. Add `mise run migration:import-weaviate`.
13. Do not activate the target generation in this step.

## Tests And Checks

- Import the same fixture batch twice and verify no duplicates.
- Simulate transient batch failures and verify bounded retry.
- Verify permanent failures are surfaced with object IDs and safe errors.
- Verify every required chunk has the expected named vector.
- Run BM25-only, vector-only, and hybrid fixture searches.
- Verify policy filters execute with each search mode.
- Verify no external provider is required in deterministic CI.
- `mise run ci`

## Acceptance Criteria

- The inactive generation contains all expected objects.
- Re-running import is idempotent.
- Weaviate owns vectorization and index construction for the normal runtime.
- Lexical, vector, filtered, and hybrid smoke tests pass.
- Import failures cannot be hidden by partial success.

## Suggested Commit Message

`feat: import corpus into weaviate`
