# 5.5: Direct Weaviate Retrieval CLI

## Goal

Replace application-owned retrieval orchestration with one direct Weaviate query used by the operator CLI and evaluation.

## Instructions

1. Implement a thin adapter around the official Weaviate client.
2. Support a bounded configuration set:
   - collection generation
   - target named vector
   - lexical properties
   - hybrid `alpha`
   - result limit
   - returned properties
   - returned score metadata
3. Add or adapt `idp-brain retrieve query`.
4. Return sanitized evidence and citation properties directly.
5. Do not port:
   - separate exact, BM25, and vector retrievers
   - reciprocal rank fusion
   - application authority or freshness reranking
   - the default application reranker registry
   - SQL-backed evidence-bundle assembly
6. Defer fetch-by-ID and explain tooling until usage proves they are necessary.
7. Keep raw queries and content out of telemetry.

## Checks

- BM25-only, vector-only, and hybrid fixture queries work
- expected evidence IDs are returned
- citations are complete
- no legacy retriever is invoked
- no application score fusion is performed
- `mise run retrieve -- "fixture query"`
- `mise run ci`

## Acceptance Criteria

The retrieval CLI is a small test and operator surface over Weaviate rather than an application-owned search engine.
