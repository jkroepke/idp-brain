# 2.4: Access Policy Models

## Goal
Add schema and models for source allowlists, ACL policy, visibility labels, sensitivity classes, and license policy metadata that later retrieval must apply before every subquery.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 2.3 is complete.
- Core source, artifact, chunk, claim, relationship, and citation tables exist.
- This step does not implement retrieval; it creates policy metadata and constraints for later retrieval steps.

## Files To Create Or Modify
- `src/idp_brain/models/access.py`
- `src/idp_brain/models/__init__.py`
- `migrations/versions/0003_access_policy_metadata.py`
- `tests/test_access_policy_models.py`

## Implementation Instructions
1. Add an `access_policies` table with policy ID, policy version, visibility label, allowed groups, allowed principals, optional source ID, optional source filter JSON, optional chunk filter JSON, default-deny flag, effective timestamps, and audit timestamps.
2. Add normalized or constrained policy label fields to `sources`, `source_versions`, `artifacts`, `facts`, `chunks`, `claims`, `relationships`, and `citations`: `visibility_label`, `sensitivity_class`, `license_policy_status`, and source allowlist status where applicable.
3. Add indexes for policy filtering on source ID, source version ID, visibility label, sensitivity class, license policy status, artifact path, language, version label, and citation IDs. These indexes are for future exact, BM25, vector, relationship, diagnostics, CLI, and MCP filtering.
4. Add model-level helpers only for constructing policy metadata. Do not add retrieval helpers that could bypass the future pre-subquery filter contract.
5. Treat caller-provided context as untrusted. The schema should support trusted access context derived from local configuration, session identity, or operator policy later.
6. Ensure unknown visibility, sensitivity, source allowlist, or license policy labels cannot accidentally become public. Use constrained values and default-deny semantics.
7. Keep ACL and policy metadata separate from source-specific business logic. Adding a new tool or repository must be a config change unless a new extractor family is needed.
8. Document in test names and comments that later retrieval must apply source allowlist, ACL, sensitivity, and license filters before exact lookup, BM25, vector search, relationship traversal, memory lookup, diagnostics, CLI output, and MCP `search`/`fetch`.

## Tests And Checks
- `mise run up`
- `mise run db:migrate`
- `uv run pytest tests/test_access_policy_models.py`
- `mise run lint`
- `mise run test`
- Include tests for default-deny policies, allowed group/principal serialization, required labels on facts and retrievable records, and indexes/constraints needed for later filter pushdown.
- Passing condition: every retrievable or citable record can carry trusted access, sensitivity, source allowlist, and license policy metadata.

## Acceptance Criteria
- Access policy records are canonical and migration-managed.
- Sources, artifacts, facts, chunks, claims, relationships, and citations carry labels required for later retrieval filtering.
- Unknown or missing policy labels fail closed.
- The schema supports pre-subquery filters for exact, BM25, vector, relationship, memory, diagnostics, CLI, and MCP retrieval paths.
- Raw unsanitized chunks are never persisted, embedded, logged, returned, or introduced by policy metadata.

## Suggested Commit Message
`feat: add access policy metadata models`
