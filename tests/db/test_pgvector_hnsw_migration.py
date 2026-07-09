from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from idp_brain.db import MigrationCheckError, assert_vector_available

MIGRATION_PATH = Path("migrations/versions/0014_embeddings_hnsw_index.py")
EXPECTED_HNSW_INDEXES = {
    "embeddings_hnsw_cosine_32_idx": "vector(32)",
    "embeddings_hnsw_cosine_64_idx": "vector(64)",
}


def test_hnsw_migration_sql_is_vector_index_only() -> None:
    migration_sql = MIGRATION_PATH.read_text()

    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration_sql
    assert "USING hnsw" in migration_sql
    assert "vector_cosine_ops" in migration_sql
    assert '32: "embeddings_hnsw_cosine_32_idx"' in migration_sql
    assert '64: "embeddings_hnsw_cosine_64_idx"' in migration_sql
    assert "vector::vector({dimensions})" in migration_sql
    assert "raw_text" not in migration_sql
    assert "raw_content" not in migration_sql
    assert "provider_payload" not in migration_sql


@pytest.mark.integration
@pytest.mark.requires_pgvector
def test_hnsw_migration_creates_expected_indexes(
    phase2_migrated_engine: Engine,
) -> None:
    assert_vector_available(phase2_migrated_engine)

    with phase2_migrated_engine.connect() as connection:
        index_rows = connection.execute(
            text(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename = 'embeddings'
                AND indexname IN (
                    'embeddings_hnsw_cosine_32_idx',
                    'embeddings_hnsw_cosine_64_idx',
                    'ix_embeddings_chunk_id',
                    'ix_embeddings_embedding_model_id',
                    'ix_embeddings_index_version_id',
                    'ix_embeddings_is_active'
                )
                """
            )
        ).all()

    index_defs = {row.indexname: row.indexdef for row in index_rows}
    for index_name, vector_type in EXPECTED_HNSW_INDEXES.items():
        assert index_name in index_defs
        assert "USING hnsw" in index_defs[index_name]
        assert vector_type in index_defs[index_name]
        assert "vector_cosine_ops" in index_defs[index_name]
        assert "is_active" in index_defs[index_name]

    assert "ix_embeddings_chunk_id" in index_defs
    assert "ix_embeddings_embedding_model_id" in index_defs
    assert "ix_embeddings_index_version_id" in index_defs
    assert "ix_embeddings_is_active" in index_defs


@pytest.mark.integration
@pytest.mark.requires_pgvector
def test_hnsw_migration_downgrade_drops_created_indexes(
    alembic_config: Config,
) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0013_chunks_bm25_index")
    command.upgrade(alembic_config, "0014_embeddings_hnsw_index")

    from idp_brain.db import create_db_engine

    engine = create_db_engine()
    try:
        with engine.connect() as connection:
            for index_name in EXPECTED_HNSW_INDEXES:
                assert (
                    connection.execute(
                        text(f"SELECT to_regclass('public.{index_name}')")
                    ).scalar_one()
                    == index_name
                )
            assert (
                connection.execute(
                    text("SELECT to_regclass('public.ix_embeddings_is_active')")
                ).scalar_one()
                == "ix_embeddings_is_active"
            )

        command.downgrade(alembic_config, "0013_chunks_bm25_index")
        with engine.connect() as connection:
            for index_name in set(EXPECTED_HNSW_INDEXES) | {"ix_embeddings_is_active"}:
                assert (
                    connection.execute(
                        text(f"SELECT to_regclass('public.{index_name}')")
                    ).scalar_one()
                    is None
                )
    finally:
        engine.dispose()
        command.upgrade(alembic_config, "head")


@pytest.mark.integration
@pytest.mark.requires_pgvector
def test_vector_migration_check_fails_clearly_without_extension(
    phase2_migrated_engine: Engine,
) -> None:
    assert_vector_available(phase2_migrated_engine)

    with phase2_migrated_engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text("DROP EXTENSION vector CASCADE"))

        with pytest.raises(MigrationCheckError, match="vector"):
            assert_vector_available(connection)

        transaction.rollback()
