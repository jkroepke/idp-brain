# 6.3: Collection Schema And Deterministic IDs

## Goal

Define versioned Weaviate collections that preserve retrieval, policy, provenance, citation, and lifecycle requirements without recreating the relational schema.

## Prerequisites

- Step 6.2 provides a healthy Weaviate runtime and client.
- Existing Pydantic domain models describe sanitized sources, versions, chunks, citations, claims, relationships, memory, and evaluation data.

## Files To Create Or Modify

- `config/weaviate.yaml`
- `src/idp_brain/store/schema.py`
- `src/idp_brain/store/ids.py`
- `src/idp_brain/store/bootstrap.py`
- domain-to-object mapping models
- schema and ID tests

## Required Collections

- `EvidenceChunk_<generation>`
- `Source_<generation>`
- `SourceVersion_<generation>`
- `IngestionRun_<generation>`
- `MemoryItem_<generation>`
- `EvaluationCase_<generation>`
- `EvaluationResult_<generation>`

Optional collections are created only for implemented use cases:

- `Claim_<generation>`
- `Entity_<generation>`
- `Change_<generation>`

## Implementation Instructions

1. Use versioned collection names or an equivalent generation strategy. Never mutate an active collection incompatibly in place.
2. Make `EvidenceChunk` the primary searchable object. Denormalize every field needed for filtering and citation into the chunk object.
3. Define explicit property types, tokenization, filterability, searchability, and index settings. Do not rely on broad auto-schema behavior.
4. Include at least:
   - stable chunk ID and deterministic UUID.
   - sanitized content and content kind.
   - source and source-version IDs.
   - URL, commit, tag, version, checksum, path, and line range.
   - language, heading, symbol, signature, package, and namespace where available.
   - source authority and freshness fields.
   - visibility, sensitivity, license, redaction, active-state, and generation fields.
   - extractor and chunking versions.
   - sanitized content hash.
   - citation payload.
5. Define named vectors for `docs`, `code`, `schema`, and `memory` where the configured Weaviate version and provider profile support them.
6. Define lexical search properties for BM25F and exact-filter properties for stable identifiers.
7. Generate UUIDs from versioned namespace inputs. Document the canonical input format for every collection.
8. Ensure the same domain object always receives the same UUID across machines and migration retries.
9. Keep references optional for the primary query path. Add references only for navigation or structured lookup; do not require reference traversal to build a citation.
10. Add an idempotent schema bootstrap command that:
    - creates missing collections.
    - validates existing collection definitions.
    - refuses incompatible drift.
    - prints a safe diff without credentials or content.
11. Store the active collection generation in configuration. Do not hide it in mutable process memory.
12. Define an exportable collection manifest containing schema, vectorizer, reranker, index, and generation settings.

## Tests And Checks

- Run schema bootstrap twice and verify the second run is a no-op.
- Verify incompatible schema drift fails safely.
- Verify deterministic IDs are stable across processes and ordering changes.
- Insert one fixture object for each required collection.
- Verify policy and citation fields are filterable and retrievable.
- Verify named-vector configuration matches the selected profiles.
- `mise run ci`

## Acceptance Criteria

- Required collections are explicit, versioned, and reproducible.
- `EvidenceChunk` contains all metadata required for filtered retrieval and citations.
- IDs are deterministic and idempotent.
- Active schema drift is detected rather than silently accepted.
- The model does not recreate every PostgreSQL table as a separate collection.

## Suggested Commit Message

`feat: define weaviate collections`
