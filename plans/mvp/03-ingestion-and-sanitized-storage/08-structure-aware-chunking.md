# 3.8: Structure Aware Chunking

## Goal
Create stable, structure-aware sanitized chunks from redacted extraction candidates while preserving provenance, source authority metadata, access labels, sensitivity labels, license labels, and citation locators.

## Prerequisites
- Phase 3.7 is complete, and only redacted or redaction-checked candidates can enter chunking.
- Phase 2 data model includes `chunks`, `citations`, `facts`, `claims`, and `relationships` or placeholders for the subset used in the MVP.
- LlamaIndex node abstractions are available if Phase 1 dependency management has added them; otherwise add them in this step according to `ARCHITECTURE.md`.

## Files To Create Or Modify
- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/ingestion/chunking/__init__.py`
- `src/idp_brain/ingestion/chunking/base.py`
- `src/idp_brain/ingestion/chunking/documents.py`
- `src/idp_brain/ingestion/chunking/structured_data.py`
- `src/idp_brain/ingestion/chunking/source_code.py`
- `src/idp_brain/ingestion/chunking/pipeline.py`
- `src/idp_brain/models/chunks.py`
- `src/idp_brain/repositories/chunks.py`
- `src/idp_brain/repositories/citations.py`
- `config/extractors.yaml`
- `tests/fixtures/chunking/`
- `tests/test_structure_aware_chunking.py`

## Implementation Instructions
1. Add a `Chunker` protocol that accepts sanitized extraction candidates and returns `SanitizedChunk` records plus citations and optional facts or claims.
2. Reject any candidate that is not marked `redacted` or `redaction_checked`.
3. Use document structure for Markdown and HTML: heading path, anchors, paragraphs, lists, tables, and code blocks. Keep code blocks attached to their nearest heading and language tag when available.
4. Use structured paths for JSON, YAML, TOML, OpenAPI, and JSON Schema: JSON Pointer, dotted keys, endpoint paths, operation IDs, schema names, property paths, required fields, enum values, constraints, and examples.
5. Add a source-code chunking interface that consumes symbol metadata from the tree-sitter source-code extractor and can later accept language-native extractors. For unsupported languages, create file-level or block-level chunks only when source code artifacts are explicitly enabled, and preserve language, package or namespace when known, symbol path when known, signature text when known, imports when known, and parent context when known.
6. Use chunk size and overlap settings from `config/extractors.yaml`; keep defaults deterministic and conservative.
7. Keep chunk IDs stable by deriving them from source ID, source version ID, artifact locator, sanitized content hash, chunker profile, structure path, and ordinal within the structure.
8. Persist only sanitized chunk text and sanitized metadata. Store citations with source ID, source URL, commit/tag/version/checksum, path or locator, line range, source type, sanitized content hash, redaction status, visibility label, sensitivity class, access label, and license policy label.
9. Store normalized facts, claims, and relationships only when an extractor emits structured values with citations. Do not invent claims from narrative text in this step.
10. Do not create embeddings or BM25 indexes in this step. Phase 4 owns embedding, vector storage, and retrieval indexes.
11. Ensure prompt-injection-like source text remains data inside sanitized chunks and is never executed or treated as instruction.

## Tests And Checks
- `uv sync`
- `uv run pytest tests/test_structure_aware_chunking.py`
- `mise run lint`
- `mise run test`
- Passing condition: sanitized fixtures produce stable chunk IDs and citations across repeated runs, structure metadata is preserved, unredacted candidates are rejected, and raw fixture secret strings never appear in persisted chunks, citations, facts, claims, or logs.

## Acceptance Criteria
- Chunking runs only after redaction.
- Markdown, HTML, structured data, OpenAPI, JSON Schema, text, and explicit source-code fallback chunks preserve meaningful structure and provenance.
- Persisted chunks and citations carry source, access, visibility, sensitivity, license policy, redaction status, extractor, chunker, and sanitized content hash metadata.
- Chunk boundaries are stable enough for incremental ingestion to compare unchanged chunks.
- No raw unsanitized chunks are persisted, embedded, logged, returned, indexed, or exposed to evaluation or LLM context.

## Suggested Commit Message
`feat: add structure aware chunking`
