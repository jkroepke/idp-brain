# 5.3: Weaviate Runtime And Collection

## Goal

Establish the target local runtime and one deliberately small, versioned searchable collection.

## Instructions

1. Replace the target Docker Compose persistence service with a pinned Weaviate image.
2. Bind HTTP, gRPC, and MCP endpoints to localhost in local development.
3. Enable the built-in MCP server and keep MCP write access disabled.
4. Add `config/weaviate.yaml` or equivalent typed settings for endpoint, authentication, collection generation, vectorizer, named vectors, tokenization, and backup backend.
5. Implement idempotent collection bootstrap.
6. Create only `EvidenceChunk_<generation>` initially.
7. Store citation fields directly on each object.
8. Use a new collection generation for incompatible vectorizer, tokenization, or index changes.
9. Add `mise run weaviate:bootstrap` and `mise run weaviate:reset`.
10. Do not recreate the relational schema as collections.

## Checks

- `docker compose config`
- readiness and collection bootstrap tests
- repeated bootstrap is idempotent
- read-only MCP authentication and collection access are verified
- a disposable volume can be deleted and recreated
- `mise run ci`

## Acceptance Criteria

A fresh runtime creates one valid versioned `EvidenceChunk` collection and exposes it through a restricted read-only MCP endpoint.
