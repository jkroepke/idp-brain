# 7.5: Weaviate Backup And Restore

## Goal

Add a Docker Compose and `mise` workflow that creates a Weaviate backup in the repository-local `backups/` directory and proves that it restores into an empty instance.

## Prerequisites

- Weaviate collections, ingestion, and retrieval are working.
- The pinned Weaviate build supports the configured backup backend.
- Local persisted objects contain sanitized data only.

## Files To Create Or Modify

- `docker-compose.yaml`
- `mise.toml`
- `.gitignore`
- `config/weaviate.yaml`
- `src/idp_brain/store/backup.py`
- `src/idp_brain/store/restore.py`
- backup and restore integration tests

## Implementation Instructions

1. Enable Weaviate's filesystem backup backend for the local profile with a bind-mounted repository directory.
2. Add `mise run weaviate:backup` that calls the supported backup API through the application client or a small repository-owned tool.
3. Use an unambiguous UTC timestamp, active generation, and backup ID.
4. Back up every active required collection and its vectors.
5. Wait for completion and fail on partial, failed, or timed-out backup operations.
6. Store a safe manifest with backup ID, Weaviate version, collection generations, object counts, schema manifest hash, and completion time.
7. Add `/backups/` to `.gitignore`.
8. Add `mise run weaviate:restore-smoke-test` that:
   - starts an empty isolated Weaviate instance.
   - restores the selected backup.
   - validates collection definitions, object counts, and vector presence.
   - runs exact, filtered, BM25-only, vector-only, hybrid, and citation fetch fixtures.
   - destroys the isolated instance.
9. Verify backups and manifests do not include provider API keys or runtime credentials.
10. Document that production retention, encryption, remote backend, replication, and recovery objectives are deployment policy.
11. Keep full rebuild from configured sources as a second recovery path.

## Tests And Checks

- `docker compose config`
- Seed sanitized fixtures.
- `mise run weaviate:backup`
- Verify a completed backup and manifest exist.
- `mise run weaviate:restore-smoke-test`
- Verify restored retrieval and citations.
- `git check-ignore backups/<generated-path>`
- `mise run ci`

## Acceptance Criteria

- Local backup uses Weaviate's supported backup API.
- Restore into an empty instance is automated and verified.
- Restored lexical, vector, hybrid, filtered, and citation behavior works.
- The backup directory is ignored by Git.
- Credentials and source content are not printed to logs.

## Suggested Commit Message

`ops: add weaviate backup and restore`
