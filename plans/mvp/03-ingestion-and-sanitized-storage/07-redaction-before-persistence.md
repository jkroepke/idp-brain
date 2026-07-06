# 3.7: Redaction Before Persistence

## Goal
Enforce redaction, sensitivity classification, source policy, and license policy before chunking, persistence, embeddings, evaluation data, retrieval logs, reranking, or LLM-facing context can receive extracted content.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 3.6 is complete.
- Phase 2 redaction and license models exist, including `redaction_events` and `license_findings`.
- `config/security.yaml`, `config/access.yaml`, and source-level license policy fields exist.

## Files To Create Or Modify
- `src/idp_brain/security/__init__.py`
- `src/idp_brain/security/redaction.py`
- `src/idp_brain/security/classification.py`
- `src/idp_brain/security/license_policy.py`
- `src/idp_brain/ingestion/redaction_stage.py`
- `src/idp_brain/models/redaction.py`
- `src/idp_brain/repositories/redaction_events.py`
- `src/idp_brain/repositories/license_findings.py`
- `config/security.yaml`
- `tests/fixtures/redaction/`
- `tests/test_redaction_before_persistence.py`

## Implementation Instructions
1. Add a redaction stage that is the only path from extractor candidates to normalized chunks, facts, claims, citations, or any persisted content fields.
2. Implement deterministic built-in redaction rules for common secret-like values: API keys, bearer tokens, private key blocks, password assignments, connection strings, cloud access keys, and email addresses when the source profile requires PII handling.
3. Load additional regex and replacement rules from `config/security.yaml`.
4. Support optional Gitleaks, detect-secrets, and Microsoft Presidio adapters only when configured. Tests and CI must pass with the deterministic built-in scanner and without external services.
5. Replace sensitive spans with stable markers such as `[REDACTED:SECRET:1]` or `[REDACTED:PII:1]`. Markers may include type and sequence number, but never the raw matched value or a reversible transform.
6. Run redaction before chunking so chunk boundaries and downstream hashes are based only on sanitized text.
7. Store `redaction_events` with source ID, source version ID, artifact ID, optional later chunk ID, rule ID, redaction type, count, confidence, scanner name, scanner version, access label, visibility label, sensitivity class, license policy label, and timestamps. Do not store raw matched values, surrounding raw context, or reversible hashes of secrets.
8. Assign or update sensitivity class, redaction status, visibility label, access label, and license policy label on every sanitized candidate.
9. Run license policy classification before records become retrievable. Store license IDs, scanner provenance, copyright findings when safe, policy status, source ID, source version ID, access label, visibility label, and sensitivity class without copying full raw file contents.
10. Add guard functions at persistence boundaries that reject any candidate not marked `redacted` or `redaction_checked`.
11. Add logging filters for ingestion diagnostics so exceptions and validation errors cannot include raw candidate text.

## Tests And Checks
- `uv run pytest tests/test_redaction_before_persistence.py`
- `mise run lint`
- `mise run test`
- A database safety check that searches persisted text columns used by ingestion for fixture secret strings and expects zero matches.
- Passing condition: known fixture secrets and PII are redacted before chunking or persistence, redaction events contain counts, rule IDs, labels, and affected record IDs without raw values, and unredacted candidates are rejected by persistence guards.

## Acceptance Criteria
- Redaction is mandatory before chunking, persistence, embeddings, evaluation data, retrieval logs, reranking, and LLM context.
- Raw unsanitized chunks and raw secret or PII values are never persisted, embedded, logged, returned, or used in diagnostics.
- Redaction events store markers, counts, rule metadata, labels, and affected record IDs only.
- Sanitized candidates carry source, access, visibility, sensitivity, license policy, and redaction status labels.
- CI uses deterministic local scanners and does not require external security services.

## Suggested Commit Message
`feat: enforce redaction before persistence`
