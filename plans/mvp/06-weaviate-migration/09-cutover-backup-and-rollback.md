# 6.9: Cutover, Backup, Restore, And Rollback

## Goal

Activate the validated Weaviate collection generation, verify recoverability, and define rollback without creating a permanent dual-store runtime.

## Prerequisites

- Step 6.8 passes all configured gates.
- The target collection generation is complete and inactive.
- A final PostgreSQL backup and migration manifest exist for the temporary migration window.

## Files To Create Or Modify

- `config/weaviate.yaml`
- `src/idp_brain/store/activation.py`
- `src/idp_brain/store/backup.py`
- `src/idp_brain/store/restore.py`
- `mise.toml`
- `.gitignore`
- cutover and restore tests

## Implementation Instructions

1. Configure a Weaviate backup backend. Local development uses a repository-local ignored filesystem directory; production backend selection is deployment configuration.
2. Create a full backup of the validated target generation before activation.
3. Add a restore smoke test that restores into an empty isolated Weaviate instance and validates:
   - collection manifests.
   - object counts.
   - content-hash aggregates.
   - vector presence.
   - exact, filtered, lexical, vector, and hybrid fixture queries.
   - stable citation fetches.
4. Activate the target generation through one explicit configuration change.
5. Make CLI, MCP, ingestion, and evaluation read the active generation from the same configuration source.
6. Add `mise run migration:cutover-check` that fails unless:
   - backup and restore passed.
   - shadow evaluation passed.
   - no incomplete batches remain.
   - required collections and vectors exist.
   - policy and citation audits pass.
7. During the short observation window, rollback may switch to the previous backend through the temporary migration flag.
8. After Step 6.10 removes PostgreSQL, rollback means reactivating the previous validated Weaviate collection generation or restoring its backup.
9. Do not dual-write indefinitely. New writes go only to the configured active backend during the observation window.
10. Document recovery point, recovery time, retention, encryption, and restore ownership for production separately from the local MVP.
11. Ignore local backup and migration artifact directories in Git.
12. Keep a complete source rebuild as a supported recovery path.

## Tests And Checks

- Create a Weaviate backup.
- Restore it into an empty instance.
- Run schema, count, hash, vector, retrieval, policy, and citation checks.
- Activate the new generation and run CLI, MCP, ingestion, and evaluation smoke tests.
- Exercise rollback to the previous validated generation.
- Verify no credentials or source content are printed by backup tooling.
- `mise run ci`

## Acceptance Criteria

- The validated Weaviate generation is active.
- Backup and restore are tested, not only configured.
- Rollback has a documented and exercised path.
- The application has one configured active write path.
- A full rebuild from configured sources remains possible.

## Suggested Commit Message

`ops: cut over retrieval to weaviate`
