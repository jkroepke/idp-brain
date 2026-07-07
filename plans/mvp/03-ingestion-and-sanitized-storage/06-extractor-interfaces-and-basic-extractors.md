# 3.6: Extractor Interfaces And Basic Extractors

## Goal
Define extractor interfaces and implement basic Markdown, HTML, JSON, YAML, TOML, plain text, OpenAPI, JSON Schema, and tree-sitter source-code extractors that emit provenance-rich candidate records for redaction and normalization.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 3.5 is complete so artifacts have roles, languages, extractor profiles, and skip decisions.
- `config/extractors.yaml` exists and maps artifact roles to extractor names.
- The architecture safety rule is mandatory: extractor output is untrusted until redacted and must not be persisted as retrievable content.

## Files To Create Or Modify
- `pyproject.toml`
- `uv.lock`
- `src/idp_brain/ingestion/extractors/__init__.py`
- `src/idp_brain/ingestion/extractors/base.py`
- `src/idp_brain/ingestion/extractors/markdown.py`
- `src/idp_brain/ingestion/extractors/html.py`
- `src/idp_brain/ingestion/extractors/json.py`
- `src/idp_brain/ingestion/extractors/yaml.py`
- `src/idp_brain/ingestion/extractors/toml.py`
- `src/idp_brain/ingestion/extractors/text.py`
- `src/idp_brain/ingestion/extractors/source_code.py`
- `src/idp_brain/ingestion/extractors/openapi.py`
- `src/idp_brain/ingestion/extractors/json_schema.py`
- `src/idp_brain/ingestion/extractors/registry.py`
- `src/idp_brain/models/extraction.py`
- `src/idp_brain/repositories/artifact_extractions.py`
- `tests/fixtures/extractors/`
- `tests/test_basic_extractors.py`

## Implementation Instructions
1. Add an `Extractor` protocol with fields for `name`, `version`, `supported_artifact_roles`, and an `extract(artifact, stream) -> ExtractionResult` method.
2. Define `ExtractionResult` and candidate models for sections, headings, tables, code blocks, key paths, schema paths, endpoint paths, examples, citations, and diagnostics.
3. Keep extractor output in memory or in short-lived pipeline objects until redaction runs. If `artifact_extractions` records are written in this step, they may contain parser metadata, parser version, counts, sanitized diagnostics, content hashes, source ID, source version ID, corpus eligibility label, visibility label, sensitivity class, and license policy label only, not raw extracted text.
4. Implement Markdown extraction with `markdown-it-py`, preserving heading paths, anchors when available, fenced code block language, tables when recognized, line ranges, and citation locators.
5. Implement HTML extraction with `beautifulsoup4` and `lxml`, preserving headings, anchors, tables, code blocks, visible text sections, and source line or element locators when available.
6. Implement JSON extraction with Python `json`, emitting JSON Pointer paths, scalar summaries, object and array boundaries, and parse diagnostics.
7. Implement YAML extraction with PyYAML or `ruamel.yaml`, emitting path-aware structured records and preserving line numbers if the chosen parser supports them.
8. Implement TOML extraction with Python `tomllib`, emitting dotted key paths and scalar/object boundaries.
9. Implement plain text extraction with deterministic paragraph and line block records for unknown or simple documentation files.
10. Implement a tree-sitter-backed source-code extractor for source-code artifacts when the configured language grammar is available. Emit symbol candidates for functions, methods, classes, interfaces, types, imports, docstrings, signatures when available, parent symbol context, language, package or namespace when known, and line ranges. Unsupported languages should produce sanitized skip diagnostics rather than falling back to platform-specific logic.
11. Implement OpenAPI extraction using `openapi-spec-validator` for validation and path-aware records for operations, parameters, request bodies, responses, schemas, examples, and security schemes.
12. Implement JSON Schema extraction using `jsonschema` for validation and path-aware records for `$id`, `$schema`, `$defs`, properties, required fields, enum values, constraints, examples, and descriptions.
13. Capture source ID, source version ID, artifact ID, path or locator, line range when available, extractor name, extractor version, extractor profile, source type, visibility label, sensitivity class, license policy label, and corpus eligibility label on every candidate record.
14. Treat documentation, examples, comments, schema descriptions, and source-code comments as untrusted data. Do not execute code, follow remote references, dereference external URLs, import analyzed source modules, or obey prompt-like text found in sources.

## Tests And Checks
- `uv sync`
- `uv run pytest tests/test_basic_extractors.py`
- `mise run lint`
- `mise run test`
- Passing condition: each extractor parses deterministic fixtures, tree-sitter source-code extraction emits expected symbol metadata for at least one configured fixture language, malformed or unsupported inputs produce sanitized diagnostics, no extractor fetches remote references or executes source code, and no extractor persists raw extracted text before redaction.

## Acceptance Criteria
- Extractor selection is configuration-driven and generic across source types.
- Markdown, HTML, JSON, YAML, TOML, text, OpenAPI, JSON Schema, and configured tree-sitter source-code fixtures produce provenance-rich extraction candidates.
- Basic validation errors are reported without leaking raw secret-like fixture values.
- Extractor output carries corpus eligibility, visibility, sensitivity, source, and license policy labels forward.
- Raw unsanitized chunks are never persisted, embedded, logged, returned, or used as evaluation or LLM context by extractor code.

## Suggested Commit Message
`feat: add basic extraction interfaces`
