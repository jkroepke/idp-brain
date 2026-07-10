# Database review focus

Read this file only for database or migration risk.

Check the changed path for ORM and Alembic consistency, safe creation and
upgrade/downgrade paths, defaults and backfills before constraints, relational
constraints and cascades, transaction boundaries and retries, PostgreSQL
extension assumptions, `pg_search` and pgvector index compatibility, filtered
query correctness, atomic index activation, and focused migration/query tests.

Report only issues demonstrated by the diff or affected execution path.
