# 2.3: Core SQLAlchemy Models

## Goal
Add the canonical SQLAlchemy and Alembic data model for configured sources, resolved versions, discovered artifacts, sanitized chunks, citations, normalized claims, and citation-backed relationships.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 1 database and migration infrastructure are complete.
- Phase 2.1 and Phase 2.2 are complete.
- PostgreSQL extensions from Phase 1 can be created in a fresh local database.

## Files To Create Or Modify
- `src/idp_brain/models/__init__.py`
- `src/idp_brain/models/base.py`
- `src/idp_brain/models/source.py`
- `src/idp_brain/models/artifact.py`
- `src/idp_brain/models/evidence.py`
- `src/idp_brain/models/claim.py`
- `src/idp_brain/models/relationship.py`
- `migrations/env.py`
- `migrations/versions/0002_core_data_model.py`
- `tests/test_core_models.py`

## Implementation Instructions
1. Create a SQLAlchemy 2 `DeclarativeBase` with deterministic naming conventions for constraints and indexes so Alembic autogeneration remains stable.
2. Add canonical tables for `sources`, `source_versions`, `source_changes`, `change_versions`, `ingestion_runs`, `artifacts`, `artifact_versions`, `artifact_extractions`, `facts`, `fact_versions`, `claims`, `claim_versions`, `claim_conflicts`, `relationships`, `relationship_versions`, `chunks`, `chunk_versions`, and `citations`.
3. Use stable string or UUID primary keys consistently. Ensure natural IDs from config, source references, and citations remain unique where later retrieval needs stable citation IDs.
4. Store source provenance on every artifact, fact, chunk, claim, relationship, and citation: source ID, source version ID, repository or artifact URL, commit SHA/tag/version/checksum when known, path or logical locator, source type, extractor name, extractor version, extractor profile, first seen timestamp, and last verified timestamp.
5. Store version lineage fields as nullable when unknown. Do not infer first or last containing versions unless evidence exists from tags, releases, branches, commits, checksums, or configured artifact versions.
6. Define `chunks.sanitized_text`, `chunks.sanitized_content_hash`, heading path, symbol path, signature text, artifact path, source type, language, artifact role, and version label. Do not create `raw_text`, `raw_content`, `unsanitized_text`, or equivalent columns.
7. Define `citations` as stable pointers to source evidence with source URL, commit/tag/version/checksum, path or locator, line range, source type, sanitized content hash, redaction status, visibility label placeholder, and sensitivity placeholder for later policy migrations.
8. Define `claims` with subject, predicate, normalized value JSON, value type, scope JSON, confidence, authority rank, and citation links. Define conflicts through `claim_conflicts` without silently resolving incompatible claims.
9. Define `relationships` as typed, versioned, citation-backed links with initial types `contains`, `defines`, `references`, `derived_from`, `cites`, `introduced_in`, `removed_in`, `changed_by`, and `conflicts_with`.
10. Keep BM25 indexes, vector storage, embedding jobs, access policy tables, redaction events, and license findings for later Phase 2 steps.
11. Update Alembic metadata loading so migrations can import the model metadata without importing ingestion, retrieval, or model-provider code.

## Tests And Checks
- `mise run up`
- `mise run db:migrate`
- `uv run pytest tests/test_core_models.py`
- `mise run lint`
- `mise run test`
- Include tests that create the schema from scratch, insert a minimal source/version/artifact/fact/sanitized chunk/citation/claim/relationship graph, and assert no table exposes raw unsanitized chunk columns.
- Passing condition: the canonical schema migrates cleanly and persists only sanitized retrievable content.

## Acceptance Criteria
- Core relational tables are canonical and migration-managed.
- Facts, chunks, citations, claims, and relationships are source-backed and version-aware.
- Conflict and relationship records preserve competing evidence rather than merging it silently.
- Unknown lineage remains unknown.
- Raw unsanitized chunks are never persisted, embedded, logged, returned, or represented by schema columns.

## Suggested Commit Message
`feat: add core sqlalchemy data model`
