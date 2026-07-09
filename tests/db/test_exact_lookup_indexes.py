from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

MIGRATION_PATH = Path("migrations/versions/0015_chunks_exact_lookup_indexes.py")
EXPECTED_INDEXES = {
    "chunks_exact_symbol_idx",
    "chunks_exact_artifact_path_idx",
    "chunks_exact_heading_idx",
    "chunks_exact_signature_idx",
    "chunks_exact_source_type_idx",
    "chunks_exact_version_idx",
}


def test_exact_lookup_migration_sql_uses_sanitized_metadata_only() -> None:
    migration_sql = MIGRATION_PATH.read_text()

    assert "chunks_exact_symbol_idx" in migration_sql
    assert "symbol_path" in migration_sql
    assert "artifact_path" in migration_sql
    assert "heading_path" in migration_sql
    assert "signature_text" in migration_sql
    assert "source_type" in migration_sql
    assert "version_label" in migration_sql
    assert "sanitized_text" not in migration_sql
    assert "raw_text" not in migration_sql
    assert "raw_content" not in migration_sql


@pytest.mark.integration
def test_exact_lookup_migration_creates_expected_indexes(
    phase2_migrated_engine: Engine,
) -> None:
    with phase2_migrated_engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename = 'chunks'
                AND indexname = ANY(:index_names)
                """
            ),
            {"index_names": list(EXPECTED_INDEXES)},
        ).all()

    index_defs = {row.indexname: row.indexdef for row in rows}
    assert EXPECTED_INDEXES <= set(index_defs)
    assert "symbol_path" in index_defs["chunks_exact_symbol_idx"]
    assert "artifact_path" in index_defs["chunks_exact_artifact_path_idx"]
    assert "heading_path" in index_defs["chunks_exact_heading_idx"]
    assert "signature_text" in index_defs["chunks_exact_signature_idx"]
    assert "source_type" in index_defs["chunks_exact_source_type_idx"]
    assert "version_label" in index_defs["chunks_exact_version_idx"]
    assert all("raw_text" not in index_def for index_def in index_defs.values())


@pytest.mark.integration
def test_exact_lookup_migration_downgrade_drops_indexes(
    alembic_config: Config,
) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0014_embeddings_hnsw_index")
    command.upgrade(alembic_config, "0015_chunks_exact_lookup_indexes")

    from idp_brain.db import create_db_engine

    engine = create_db_engine()
    try:
        with engine.connect() as connection:
            for index_name in EXPECTED_INDEXES:
                assert (
                    connection.execute(
                        text(f"SELECT to_regclass('public.{index_name}')")
                    ).scalar_one()
                    == index_name
                )

        command.downgrade(alembic_config, "0014_embeddings_hnsw_index")
        with engine.connect() as connection:
            for index_name in EXPECTED_INDEXES:
                assert (
                    connection.execute(
                        text(f"SELECT to_regclass('public.{index_name}')")
                    ).scalar_one()
                    is None
                )
    finally:
        engine.dispose()
        command.upgrade(alembic_config, "head")
