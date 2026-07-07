# 4.12: Evidence Bundle Contract

## Goal
Define and implement the sanitized evidence bundle contract returned by retrieval services and later reused by CLI and MCP search/fetch tools.

## Prerequisites
- Step 4.9 guarantees filtered candidate scopes.
- Step 4.10 produces fused candidate diagnostics.
- Step 4.11 optionally reranks sanitized candidates.
- Phase 3 stores citations, sanitized content hashes, redaction status, visibility labels, and source provenance.
- CLI and MCP implementation is intentionally Phase 5 or later; this step only prepares retrieval service contracts those surfaces must consume.

## Files To Create Or Modify
- `src/idp_brain/retrieval/evidence.py`
- `src/idp_brain/retrieval/service.py`
- `src/idp_brain/retrieval/models.py`
- `tests/retrieval/test_evidence_bundle_contract.py`
- `tests/retrieval/test_evidence_bundle_snapshots.py`

## Implementation Instructions
1. Define Pydantic models for `EvidenceBundle`, `EvidenceItem`, `Citation`, `CorpusEligibilityFilterResult`, `ConflictMarker`, `RetrievalDiagnostics`, and `TokenBudgetEstimate`.
   - `EvidenceItem` must contain selected chunk or memory IDs, sanitized excerpts or summaries, and citation IDs only; full `Citation` objects live in the bundle-level citation list.
2. Include the fields required by `ARCHITECTURE.md`: query, normalized query intent, selected chunk IDs, sanitized excerpts, selected memory item IDs and sanitized summaries when used, citations, source authority ranking, freshness metadata, conflict markers, corpus eligibility filter result, redaction status, and token budget estimate.
3. Define `Citation` with source ID, source URL, commit/tag/version/checksum, path or locator, line range when available, source type, sanitized content hash, redaction status, and visibility label.
4. Represent relationship-derived evidence with relationship path metadata: relationship type, direction, depth, source entity or chunk ID, target entity or chunk ID, and citation IDs for the selected endpoint evidence. Do not include raw edge payloads or ineligible endpoint metadata.
5. Build evidence items only from filtered, fused, and reranked candidates. Fetch sanitized excerpts from `chunks.sanitized_text` or sanitized excerpt fields only.
6. Require every evidence item, including relationship-derived entity or chunk candidates, to have at least one citation. Candidates without citations must be dropped or marked as diagnostics, not returned as evidence.
7. Include conflict markers when the active profile is `conflict_search` or when selected claims have competing evidence. Do not silently merge conflicting source claims.
8. Include retrieval diagnostics that show score components, rank positions, source metadata, filters applied, index path used, relationship path metadata, query profile, active index version, and competing candidates after filtering.
9. Enforce token budgets by truncating sanitized excerpts at evidence assembly time. Truncation must preserve citation IDs and sanitized content hashes.
10. Make the contract serializable to JSON for future CLI and MCP use. The later CLI/MCP `search`, `fetch`, and `explain_search` surfaces must return sanitized evidence only through this contract or a narrower derivative; they are not implemented in Phase 4.
11. Do not include raw source text, raw local cache paths, raw provider payloads, raw embeddings, ineligible counts, or secrets in the bundle.
12. Add snapshot tests with deterministic fixture IDs so contract changes are intentional.

## Tests And Checks
- `uv run pytest tests/retrieval/test_evidence_bundle_contract.py`
- `uv run pytest tests/retrieval/test_evidence_bundle_snapshots.py`
- Test that every returned evidence item has a citation and sanitized content hash.
- Test that evidence items reference citation IDs only and do not duplicate citation source payloads or source text.
- Test that relationship-derived evidence includes bounded path metadata and citation-backed endpoint evidence without raw relationship payloads.
- Test that raw secret fixture text is absent while redaction markers remain.
- Test that token-budget truncation never removes citation IDs or redaction status.
- Test that conflict markers include competing allowed citations for conflict queries.
- Test JSON serialization and stable snapshot output.

## Acceptance Criteria
- Retrieval returns evidence bundles, not raw untrusted context.
- Evidence content is sanitized, citation-backed, filter-safe, and token-budgeted.
- Evidence items expose sanitized excerpts or summaries with citation IDs only.
- Relationship-derived entity and chunk candidates are citation-backed, bounded, and represented without expanding corpus eligibility.
- Diagnostics are useful without leaking ineligible existence, raw chunks, embeddings, or provider payloads.
- The contract is ready for downstream CLI and MCP retrieval surfaces, including `search`, `fetch`, and `explain_search`, while their implementation remains out of Phase 4.
- Source conflicts can be exposed with provenance instead of being silently collapsed.

## Suggested Commit Message
`feat: add evidence bundle contract`
