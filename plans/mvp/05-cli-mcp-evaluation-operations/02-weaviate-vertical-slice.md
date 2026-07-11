# 5.2: Weaviate Vertical Slice

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
5. Include content and complete citation properties on each object.
6. Query the object through the official Python client.
7. Enable the built-in MCP server and query the same collection through `/v1/mcp`.
8. Keep the legacy stack only long enough to complete this proof. Do not dual-write production paths or compare raw scores.

## Checks

- the fixture is redacted before the Weaviate call
- ingestion and hybrid retrieval succeed
- MCP returns sanitized content and citation properties
- write tools are disabled
- no new generic persistence, vector-store, fusion, evidence-bundle, or MCP abstraction is introduced
- `mise run ci`

## Acceptance Criteria

A single source can be rebuilt into Weaviate and retrieved through both the Python client and built-in MCP. This proves the target architecture before destructive cleanup.
