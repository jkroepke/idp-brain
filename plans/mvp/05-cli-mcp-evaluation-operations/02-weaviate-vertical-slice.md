# 5.2: Weaviate Vertical Slice

## Mandatory Prerequisite

Read and apply [Step 5.0](00-weaviate-reset-rules.md) before changing code.

Step 5.0 overrides behavior implied by the existing PostgreSQL retrieval implementation. Do not use the current codebase as a compatibility specification.

In particular, this vertical slice does not require query-time corpus eligibility derivation, mandatory application filters, an exact retriever, authority or freshness adjustment, separate citation objects, an evidence bundle, or custom MCP `fetch` and `explain_search` tools.

## Goal

Prove the smallest complete Weaviate path before deleting the legacy stack:

```text
fixture source
  -> existing fetch/extract/redact/chunk pipeline
  -> EvidenceChunk object
  -> Weaviate
  -> official Python client hybrid query
  -> built-in read-only MCP query
```

## Instructions

1. Add the pinned Weaviate Python client and a pinned local Weaviate service without yet building a compatibility framework.
2. Select one deterministic fixture source already covered by ingestion tests.
3. Reuse the existing extraction, redaction, and chunking front half.
4. Map one sanitized chunk shape directly to one temporary `EvidenceChunk` collection.
5. Include sanitized content and citation properties directly on each object.
6. Query the object through one official Python client hybrid query.
7. Enable the built-in MCP server and query the same collection through `/v1/mcp`.
8. Keep the legacy stack only long enough to complete this proof. Do not dual-write production paths or compare raw scores.
9. Do not call or adapt the legacy corpus filters, exact/BM25/vector orchestration, RRF, authority/freshness ranking, evidence assembler, citation fetcher, reranker registry, or custom MCP server.

## Checks

- the fixture is redacted before the Weaviate call
- ingestion and hybrid retrieval succeed
- MCP returns sanitized content and citation properties
- write tools are disabled
- no query-time eligibility engine or mandatory hidden filter layer is introduced
- no exact retriever, authority/freshness adjustment, separate citation entity, evidence bundle, custom `fetch`, or custom `explain_search` tool is introduced
- no new generic persistence, vector-store, fusion, evidence-bundle, or MCP abstraction is introduced
- `mise run ci`

## Acceptance Criteria

A single source can be rebuilt into Weaviate and retrieved through both the Python client and built-in MCP. The slice is intentionally smaller than the legacy feature set and proves the target architecture without porting removed capabilities.
