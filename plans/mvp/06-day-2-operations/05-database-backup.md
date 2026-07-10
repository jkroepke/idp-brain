# 6.5: Docker Compose Database Backup

## Goal
Add a Docker Compose backup task that creates a PostgreSQL backup in the repository-local `backups/` directory and verify that the backup can be restored.

## Prerequisites
- The PostgreSQL service and migrations are working.
- `docker-compose.yaml` already defines the database connection through environment variables or Compose secrets suitable for local development.
- The backup contains only the local database selected by the configured connection settings.

## Files To Create Or Modify
- `docker-compose.yaml`
- `mise.toml`
- `.gitignore`
- Optional: `scripts/db-backup.sh`
- Optional: `scripts/db-restore-smoke-test.sh`
- Tests for backup naming, failure handling, and restore verification

## Implementation Instructions
1. Add a one-shot Docker Compose service named `db-backup` under an operations or tools profile.
2. Run the PostgreSQL 18 `pg_dump` client from a pinned image compatible with the database server.
3. Write each backup to the bind-mounted repository directory `./backups:/backups`.
4. Use an unambiguous UTC timestamp and database name in the filename. Write to a temporary filename first and atomically rename it only after `pg_dump` succeeds.
5. Use a restorable archive format with compression and include schema, data, extensions, ownership policy, and required metadata according to the local restore contract.
6. Make the task fail on connection errors, partial output, an empty archive, or a non-zero `pg_dump` exit code. Remove temporary files after failure.
7. Add a documented `mise run db:backup` task that delegates to `docker compose run --rm db-backup`.
8. Add `/backups/` to `.gitignore`. Do not commit database archives, temporary backup files, or restored data directories.
9. Add a restore smoke test that creates a temporary PostgreSQL database, restores the newest fixture backup, verifies migrations and required extensions, checks representative row counts or hashes, and removes the temporary database.
10. Never print database passwords, connection URLs with credentials, raw source content, or archive contents to logs.

## Tests And Checks
- `docker compose config`
- `mise run up`
- `mise run db:migrate`
- Seed sanitized fixture data.
- `mise run db:backup`
- Verify exactly one new non-empty archive exists below `backups/` and no temporary file remains.
- Run the restore smoke test and confirm required extensions, migrations, and fixture records are present.
- `git check-ignore backups/<generated-file>`
- `mise run ci`

## Acceptance Criteria
- `mise run db:backup` creates a timestamped archive below `backups/` through Docker Compose.
- Failed backups do not leave a completed-looking archive.
- The newest archive restores into an empty temporary database and passes extension, migration, and fixture checks.
- The complete `backups/` directory is ignored by Git.
- Credentials and stored source content are not written to console logs.

## Suggested Commit Message
`ops: add docker compose database backup`
