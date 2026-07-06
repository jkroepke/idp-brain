# 2.8: Model And Migration Tests

## Goal
Add a focused test suite that proves Phase 2 configuration, SQLAlchemy models, and Alembic migrations recreate the canonical data model and preserve the MVP safety contracts.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 2.1 through Phase 2.7 are complete.
- `mise run up` starts an ephemeral local PostgreSQL service with required extensions.
- Example configs validate locally without external services.

## Files To Create Or Modify
- `tests/conftest.py`
- `tests/test_example_configs.py`
- `tests/test_model_metadata.py`
- `tests/test_migration_upgrade.py`
- `tests/test_schema_safety_contracts.py`
- `.github/workflows/ci.yaml` if CI needs to include the new tests through existing `mise run ci`

## Implementation Instructions
1. Add fixtures that create a clean database, run Alembic upgrades from base to head, and dispose of connections between tests.
2. Test that every required config file loads through `load_config_dir()` and that active embedding/reranker profiles are deterministic local/mock providers in CI.
3. Test that Alembic can rebuild the Phase 2 schema from scratch, including `sources`, `source_versions`, `source_changes`, `change_versions`, `ingestion_runs`, `artifacts`, `artifact_versions`, `artifact_extractions`, `facts`, `fact_versions`, `chunks`, `chunk_versions`, `citations`, `claims`, `claim_versions`, `claim_conflicts`, `relationships`, `relationship_versions`, `access_policies`, `redaction_events`, `license_findings`, `retrieval_events`, `index_versions`, `embedding_models`, `embedding_jobs`, and `embeddings`.
4. Test required foreign keys, uniqueness constraints, nullable unknown-lineage fields, and filter indexes needed for source, ACL, sensitivity, license, version, exact lookup, citation, and future retrieval filtering.
5. Add schema safety tests that fail if retrievable, embedding, event, or job tables contain columns named like `raw_text`, `raw_content`, `unsanitized_text`, `secret_value`, `pii_value`, `prompt_text`, or provider raw response fields.
6. Add insert tests for a minimal source/version/artifact/fact/sanitized chunk/citation/claim/relationship graph with access labels, redaction marker metadata, license finding, inactive index version, deterministic embedding model, and queued embedding job.
7. Add checks that `retrieval_events` store sanitized diagnostics and IDs rather than full chunks or untrusted context.
8. Keep external APIs disabled in tests. Use deterministic local/mock embedding and reranking fixtures only; do not call OpenAI, Jina, BAAI, Cohere, LiteLLM, vLLM, BentoML, KServe, Tika, Unstructured, Presidio, ScanCode, ORT, or remote repositories.
9. Ensure `mise run ci` invokes the Phase 2 tests against an ephemeral database. GitHub Actions remains validation-only and must not promote indexes or persist ingestion output.

## Tests And Checks
- `mise run up`
- `IDP_BRAIN_CONFIRM_RESET=1 mise run db:reset`
- `mise run db:migrate`
- `uv run pytest tests/test_example_configs.py tests/test_model_metadata.py tests/test_migration_upgrade.py tests/test_schema_safety_contracts.py`
- `mise run test`
- `mise run ci`
- Passing condition: the config examples, model metadata, migrations, safety contracts, and minimal insert graph all pass with no external service calls.

## Acceptance Criteria
- Phase 2 schema can be rebuilt from an empty database in local development and CI.
- Tests prove all required canonical tables and key policy/indexing tables exist.
- Tests fail on raw unsanitized chunk persistence, unsafe event logging, or missing access/license/sensitivity metadata.
- Tests verify ACL, source, sensitivity, and license metadata needed for later pre-subquery filtering.
- Apache ACE, memory UX, embedding fine-tuning, production HA, remote model serving, and external model calls remain out of MVP.

## Suggested Commit Message
`test: add model and migration coverage`
