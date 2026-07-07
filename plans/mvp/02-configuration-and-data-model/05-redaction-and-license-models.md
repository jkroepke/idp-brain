# 2.5: Redaction And License Models

## Goal
Add redaction, license, and sanitized event tables so ingestion can record policy decisions without storing raw secrets, PII, disallowed chunks, or unsafe retrieval logs.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 2.4 is complete.
- Core records carry source, visibility, sensitivity, and license policy metadata.
- This step creates models and migrations only; scanner integrations run in later ingestion steps.

## Files To Create Or Modify
- `src/idp_brain/models/redaction.py`
- `src/idp_brain/models/license.py`
- `src/idp_brain/models/events.py`
- `src/idp_brain/models/__init__.py`
- `migrations/versions/0004_redaction_license_events.py`
- `tests/test_redaction_license_models.py`

## Implementation Instructions
1. Add `redaction_events` with ingestion run ID, source ID, source version ID, artifact ID, optional chunk ID, detector name, detector version, rule ID, marker, match count, location locator, sanitized content hash, redaction profile, severity, and timestamps.
2. Store redaction markers and counts only. Do not store matched secret values, PII values, raw line text, raw chunks, raw source excerpts, or provider prompts.
3. Add `license_findings` with source ID, source version ID, artifact ID, scanner name, scanner version, license expression or SPDX ID, copyright notice when allowed, finding location, confidence, policy status, and timestamps.
4. Add `retrieval_events` as a sanitized MVP event table. Retrieval events must store query hash, sanitized query preview or token counts, trusted filters, selected IDs, ranking diagnostics JSON, redaction status, corpus eligibility filter result, and nullable active index version ID, but never full unsanitized chunks or sensitive source text. Because `index_versions` is added in Step 2.6, keep this column nullable and non-blocking until that migration can add the foreign key.
5. Keep scanner families configurable: Gitleaks or detect-secrets for secret-like values, Microsoft Presidio for PII, and ScanCode Toolkit or OSS Review Toolkit for license metadata. Do not require these tools to run in this step.
6. Add constraints or tests that prevent accidental `raw_value`, `secret_value`, `pii_value`, `raw_text`, `unsanitized_text`, or `prompt_text` columns in redaction and event tables.
7. Ensure event records can link back to citations, chunks, artifacts, ingestion runs, and source versions by ID so policy and retrieval decisions are auditable.
8. Do not implement redaction execution, retrieval logging, LLM context assembly, or external scanner calls in this step.

## Tests And Checks
- `mise run up`
- `mise run db:migrate`
- `uv run pytest tests/test_redaction_license_models.py`
- `mise run lint`
- `mise run test`
- Include tests that insert a redaction event using only marker/count metadata, insert a license finding, insert a sanitized retrieval event without requiring `index_versions`, and assert unsafe raw-value columns do not exist.
- Passing condition: policy events are auditable without persisting raw secrets, PII, unsafe chunks, or unsanitized retrieval context.

## Acceptance Criteria
- Redaction events record what was redacted without storing the sensitive value.
- License findings record scanner provenance and policy status for later filtering.
- Retrieval and policy event records are sanitized by schema contract.
- The model supports the release gates for secret leakage, PII leakage, license filtering, and no uncited context.
- Raw unsanitized chunks are never persisted, embedded, logged, returned, or represented by event columns.

## Suggested Commit Message
`feat: add redaction and license models`
