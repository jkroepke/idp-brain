# 3.5: Artifact Discovery

## Goal
Classify fetched artifacts by path, type, language, generated status, vendored status, artifact role, and extractor profile while applying include and exclude rules before extraction.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 3.3 and Phase 3.4 are complete.
- Phase 2 data model includes `artifacts`, `artifact_versions`, and fields for artifact role, language, generated status, vendored status, checksums, corpus eligibility labels, sensitivity class, and license policy status.
- Source configuration supports include and exclude paths plus extractor profile names.

## Files To Create Or Modify
- `src/idp_brain/ingestion/discovery/__init__.py`
- `src/idp_brain/ingestion/discovery/classifier.py`
- `src/idp_brain/ingestion/discovery/linguist.py`
- `src/idp_brain/ingestion/discovery/path_rules.py`
- `src/idp_brain/repositories/artifacts.py`
- `config/extractors.yaml`
- `tests/fixtures/discovery/`
- `tests/test_artifact_discovery.py`

## Implementation Instructions
1. Add an `ArtifactDiscoveryService` that consumes fetched `SourceSnapshot` records and updates artifact discovery metadata before extraction.
2. Apply source `include_paths` and `exclude_paths` using normalized POSIX-style relative paths. Exclude rules win over include rules unless a source profile explicitly sets an override with an auditable reason.
3. Exclude generated and vendored files by default for code retrieval, matching the architecture. Allow opt-in through source or extractor profile fields such as `include_generated: true` or `include_vendored: true`.
4. Preserve every default skip and override decision as an auditable discovery field: `included`, `skipped`, `skip_reason`, `generated`, `vendored`, `override_reason`, and `discovery_rule_version`.
5. Add a GitHub Linguist adapter for language, generated-file, vendored-file, and repository language classification when the dependency is available.
6. Add a deterministic fallback classifier for CI and minimal local installs using file extensions, common vendored path patterns, common generated-file markers, MIME guesses, and fixture expectations. Tests must not require Ruby, GitHub Linguist, or network access.
7. Assign artifact roles such as `documentation`, `source_code`, `schema`, `openapi_spec`, `json_schema`, `example`, `test`, `changelog`, `license`, `generated`, `vendored`, and `unknown`.
8. Assign extractor profiles from `config/extractors.yaml` based on source type, artifact role, language, and path rules. Do not hardcode platform-specific catalogs.
9. Persist only artifact metadata and discovery diagnostics. Do not persist raw artifact bodies, extracted text, chunks, embeddings, or LLM context.
10. Carry source ID, source version ID, corpus eligibility label, visibility label, sensitivity class, license policy label, source priority, and checksums onto discovery-updated artifact records.

## Tests And Checks
- `uv run pytest tests/test_artifact_discovery.py`
- `mise run lint`
- `mise run test`
- Passing condition: include/exclude rules are deterministic, generated and vendored artifacts are excluded by default, explicit profile overrides are auditable, extractor profiles are assigned, and tests pass without GitHub Linguist or network access.

## Acceptance Criteria
- Artifact discovery runs after fetch and before extraction.
- Generated and vendored code artifacts are skipped by default unless a source profile opts in with an auditable reason.
- Include and exclude behavior is stable across local and CI runs.
- Artifact metadata carries corpus eligibility, visibility, sensitivity, source, and license policy labels.
- Raw unsanitized artifact content is never persisted, embedded, logged, returned, or sent to later services during discovery.

## Suggested Commit Message
`feat: add artifact discovery`
