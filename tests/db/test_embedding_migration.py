from __future__ import annotations

import pytest
from sqlalchemy import Engine, inspect, text

pytestmark = pytest.mark.integration


def test_embedding_migration_adds_active_vector_bookkeeping(
    phase2_migrated_engine: Engine,
) -> None:
    inspector = inspect(phase2_migrated_engine)
    embedding_columns = {
        column["name"]
        for column in inspector.get_columns("embeddings", schema="public")
    }
    job_columns = {
        column["name"]
        for column in inspector.get_columns("embedding_jobs", schema="public")
    }
    embedding_indexes = {
        index["name"] for index in inspector.get_indexes("embeddings", schema="public")
    }

    assert {
        "sanitized_content_hash",
        "is_active",
        "updated_at",
    } <= embedding_columns
    assert "sanitized_content_hash" in job_columns
    assert "ix_embeddings_active_scope" in embedding_indexes

    with phase2_migrated_engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert revision == "0015_chunks_exact_lookup_indexes"
