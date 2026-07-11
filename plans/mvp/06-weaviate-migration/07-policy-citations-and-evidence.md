# 6.7: Corpus Eligibility, Citations, And Evidence Bundles

## Goal

Prove that the Weaviate path preserves server-owned corpus eligibility, stable citation fetches, redaction rules, and the evidence bundle contract.

## Prerequisites

- Step 6.6 returns Weaviate retrieval candidates.
- `EvidenceChunk` contains denormalized policy and citation fields.
- Existing redaction and eligibility fixtures are available.

## Files To Create Or Modify

- `src/idp_brain/retrieval/filters.py`
- `src/idp_brain/retrieval/evidence.py`
- `src/idp_brain/retrieval/citations.py`
- `src/idp_brain/mcp/tools.py`
- `config/corpus.yaml`
- security and evidence tests

## Implementation Instructions

1. Build one typed filter builder for Weaviate requests.
2. Every retrieval request must include applicable filters for:
   - source allowlist.
   - visibility.
   - sensitivity.
   - license policy.
   - redaction status.
   - source version or release scope.
   - active object state.
   - active collection generation.
   - memory retention and expiry when memory is queried.
3. Caller-provided context may narrow results but may never expand the server-derived scope.
4. Do not fetch a broad result set and apply security filters only in Python.
5. Store all fields required to build a citation on `EvidenceChunk` so citation assembly does not depend on a relational join.
6. Preserve stable public citation IDs. Resolve them to deterministic Weaviate object IDs or an indexed citation property.
7. Implement `fetch` as a deterministic object fetch or equality-filtered lookup, followed by the same eligibility checks.
8. Preserve source URL, commit/tag/version/checksum, path, line range, content hash, source type, visibility, sensitivity, license, and redaction metadata.
9. Evidence bundles must contain sanitized excerpts only.
10. Explain output may report applied filter categories and exclusion counts, but not hidden allowlist contents or sensitive policy values.
11. Reject any imported object missing required policy or citation metadata before activation.
12. Add regression tests for stale versions, conflicting evidence, inactive objects, expired memory, and denied licenses.

## Tests And Checks

- Verify every retriever method invokes the shared filter builder.
- Verify denied objects are not returned by exact, lexical, vector, hybrid, structured, or fetch paths.
- Verify caller hints cannot widen scope.
- Verify citations remain stable across re-import and collection generations.
- Verify evidence excerpts match sanitized stored content hashes.
- Verify missing citation or policy fields block activation.
- `mise run ci`

## Acceptance Criteria

- Eligibility filters execute inside every Weaviate request.
- Citation and fetch behavior no longer requires PostgreSQL joins.
- Stable public IDs survive the migration.
- Evidence bundles preserve the existing safety contract.
- Raw or denied content cannot appear through diagnostics or fetch paths.

## Suggested Commit Message

`feat: enforce policy in weaviate retrieval`
