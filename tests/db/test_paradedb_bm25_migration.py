from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from idp_brain.db import MigrationCheckError, assert_pg_search_available

MIGRATION_PATH = Path("migrations/versions/0013_chunks_bm25_index.py")
EXPECTED_BM25_FIELDS = {
    "id",
    "sanitized_text",
    "heading_path",
    "symbol_path",
    "signature_text",
    "artifact_path",
    "source_type",
    "language",
    "version_label",
    "visibility_label",
    "sensitivity_class",
    "license_policy_status",
    "source_id",
    "artifact_role",
}


def test_bm25_migration_sql_uses_sanitized_chunk_fields_only() -> None:
    migration_sql = MIGRATION_PATH.read_text()

    assert "CREATE INDEX" in migration_sql
    assert "chunks_bm25_idx" in migration_sql
    assert "USING bm25" in migration_sql
    assert "sanitized_text" in migration_sql
    assert "raw_text" not in migration_sql
    assert "raw_content" not in migration_sql
    assert "artifact_extractions" not in migration_sql


@pytest.mark.integration
def test_bm25_migration_creates_expected_index(
    phase2_migrated_engine: Engine,
) -> None:
    with phase2_migrated_engine.connect() as connection:
        assert_pg_search_available(phase2_migrated_engine)

        indexdef = connection.execute(
            text(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename = 'chunks'
                AND indexname = 'chunks_bm25_idx'
                """
            )
        ).scalar_one()

    assert "USING bm25" in indexdef
    assert "key_field=id" in indexdef.replace(" ", "")
    for field in EXPECTED_BM25_FIELDS:
        assert field in indexdef
    assert "raw_text" not in indexdef
    assert "raw_content" not in indexdef


@pytest.mark.integration
def test_bm25_migration_downgrade_drops_index(
    alembic_config: Config,
) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0012_embedding_jobs_vectors")
    command.upgrade(alembic_config, "0013_chunks_bm25_index")

    from idp_brain.db import create_db_engine

    engine = create_db_engine()
    try:
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT to_regclass('public.chunks_bm25_idx')")
                ).scalar_one()
                == "chunks_bm25_idx"
            )

        command.downgrade(alembic_config, "0012_embedding_jobs_vectors")
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT to_regclass('public.chunks_bm25_idx')")
                ).scalar_one()
                is None
            )
    finally:
        engine.dispose()
        command.upgrade(alembic_config, "head")


@pytest.mark.integration
def test_pg_search_migration_check_fails_clearly_without_extension(
    phase2_migrated_engine: Engine,
) -> None:
    assert_pg_search_available(phase2_migrated_engine)

    with phase2_migrated_engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text("DROP EXTENSION pg_search CASCADE"))

        with pytest.raises(MigrationCheckError, match="pg_search"):
            assert_pg_search_available(connection)

        transaction.rollback()
