# 2.4: Corpus Eligibility Policy Models

## Goal
Add schema and models for global corpus eligibility metadata that later retrieval must apply before every subquery. The MVP has private invited users who can all see the same approved corpus, so this step must not add per-caller or role-based retrieval controls.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 2.3 is complete.
- Core source, artifact, chunk, claim, relationship, and citation tables exist.
- This step does not implement retrieval; it creates corpus eligibility metadata, constraints, and indexes for later retrieval steps.
- Target sources are public MIT or Apache-2.0 licensed materials. Anything with unknown, proprietary, incompatible, or unreviewed licensing must fail closed until explicitly marked allowed.

## Files To Create Or Modify
- `src/idp_brain/models/policy.py`
- `src/idp_brain/models/__init__.py`
- `src/idp_brain/models/source.py`
- `src/idp_brain/models/artifact.py`
- `src/idp_brain/models/evidence.py`
- `src/idp_brain/models/claim.py`
- `src/idp_brain/models/relationship.py`
- `migrations/versions/0003_corpus_eligibility_metadata.py`
- `tests/test_corpus_eligibility_models.py`

## Implementation Instructions
1. Do not create caller-specific policy tables and do not model per-caller permissions.
2. Add a small `corpus_policy_defaults` table with policy ID, policy version, source allowlist default, allowed license IDs, allowed license policy statuses, allowed sensitivity classes, allowed visibility labels, allowed redaction statuses, effective timestamps, and audit timestamps. This is global corpus eligibility, not caller-specific visibility.
3. Add constrained corpus eligibility fields to `sources`, `source_versions`, `artifacts`, `facts`, `chunks`, `claims`, `relationships`, and `citations`: `source_allowlisted`, `visibility_label`, `sensitivity_class`, `license_policy_status`, `license_id`, and `redaction_status` where they are not already present.
4. Use fail-closed defaults: `source_allowlisted = false`, `visibility_label = 'invited_users'`, `sensitivity_class = 'unknown'`, `license_policy_status = 'unknown'`, and `redaction_status = 'unknown'` unless an ingestion or policy step has explicit evidence.
5. Constrain license IDs for retrievable MVP records to `MIT` and `Apache-2.0` when `license_policy_status = 'allowed'`. Allow `license_id` to remain null only when `license_policy_status` is `unknown` or `review_required`.
6. Add indexes for filter pushdown on source ID, source version ID, source allowlist status, visibility label, sensitivity class, license policy status, redaction status, artifact path, language, version label, and citation IDs. These indexes are for future exact, BM25, vector, relationship, diagnostics, CLI, and MCP filtering.
7. Add model-level helpers or constants only for constructing corpus eligibility metadata. Do not add retrieval helpers that could bypass the future pre-subquery filter contract.
8. Treat caller-provided context as untrusted ranking or disambiguation input only. It must never expand source scope or mark ineligible records retrievable.
9. Keep corpus eligibility metadata separate from source-specific business logic. Adding a new tool or repository must be a config change unless a new extractor family is needed.
10. Document in test names and comments that later retrieval must apply source allowlist, license, sensitivity, redaction, version, and active-index filters before exact lookup, BM25, vector search, relationship traversal, memory lookup, diagnostics, CLI output, and MCP `search`/`fetch`.

## Tests And Checks
- `mise run up`
- `mise run db:migrate`
- `uv run pytest tests/test_corpus_eligibility_models.py`
- `mise run lint`
- `mise run test`
- Include tests for fail-closed defaults, public invited-user visibility, MIT/Apache-2.0 license constraints, required labels on facts and retrievable records, and indexes/constraints needed for later filter pushdown.
- Passing condition: every retrievable or citable record can carry source allowlist, license, sensitivity, redaction, visibility, and version metadata without introducing per-caller filtering.

## Acceptance Criteria
- Corpus eligibility defaults are canonical and migration-managed.
- Sources, artifacts, facts, chunks, claims, relationships, and citations carry labels required for later retrieval eligibility filtering.
- Unknown or missing source allowlist, license, sensitivity, visibility, or redaction labels fail closed.
- The schema supports pre-subquery corpus eligibility filters for exact, BM25, vector, relationship, memory, diagnostics, CLI, and MCP retrieval paths.
- The MVP does not contain per-caller policy tables.
- Raw unsanitized chunks are never persisted, embedded, logged, returned, or introduced by policy metadata.

## Suggested Commit Message
`feat: add corpus eligibility metadata models`
