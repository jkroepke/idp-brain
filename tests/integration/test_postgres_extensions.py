"""Behavior smoke tests for PostgreSQL retrieval extensions."""

from __future__ import annotations

import re
from uuid import uuid4

import pytest
from sqlalchemy import Connection, text

from idp_brain.db import create_db_engine

_IDENTIFIER_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")
_REQUIRED_EXTENSIONS = {"pg_search", "pg_trgm", "vector"}

_ACCESS_FILTERS_SQL = """
source_allowlisted = true
AND access_policy_id = 'public'
AND visibility_label = 'public'
AND sensitivity_class = 'public'
AND license_policy_status = 'allowed'
"""


def _quoted_identifier(identifier: str) -> str:
    if not _IDENTIFIER_PATTERN.fullmatch(identifier):
        raise ValueError(f"Unsafe SQL identifier: {identifier}")

    return f'"{identifier}"'


def _unique_identifier(prefix: str, suffix: str) -> str:
    identifier = f"{prefix}_{suffix}"
    _quoted_identifier(identifier)
    return identifier


def _assert_required_extensions_present(connection: Connection) -> None:
    extension_names = set(
        connection.execute(
            text(
                """
                SELECT extname
                FROM pg_extension
                WHERE extname IN ('vector', 'pg_search', 'pg_trgm')
                """
            )
        ).scalars()
    )

    missing_extensions = sorted(_REQUIRED_EXTENSIONS - extension_names)
    assert not missing_extensions, "Missing PostgreSQL extensions: " + ", ".join(
        missing_extensions
    )


@pytest.mark.integration
def test_postgres_extensions_support_bm25_and_hnsw_queries() -> None:
    suffix = uuid4().hex
    schema_name = _unique_identifier("idp_brain_smoke_schema", suffix)
    table_name = _unique_identifier("idp_brain_smoke_fixture", suffix)
    bm25_index_name = _unique_identifier("idp_brain_smoke_bm25", suffix)
    hnsw_index_name = _unique_identifier("idp_brain_smoke_hnsw", suffix)

    schema = _quoted_identifier(schema_name)
    table = f"{schema}.{_quoted_identifier(table_name)}"
    bm25_index = _quoted_identifier(bm25_index_name)
    hnsw_index = _quoted_identifier(hnsw_index_name)

    expected_id = "public-semantic-retrieval"
    engine = create_db_engine()
    schema_created = False

    try:
        with engine.begin() as connection:
            _assert_required_extensions_present(connection)

            connection.execute(text(f"CREATE SCHEMA {schema}"))
            schema_created = True
            connection.execute(
                text(
                    f"""
                    CREATE TABLE {table} (
                        id text PRIMARY KEY,
                        sanitized_text text NOT NULL,
                        source_allowlisted boolean NOT NULL DEFAULT true,
                        access_policy_id text NOT NULL DEFAULT 'public',
                        visibility_label text NOT NULL DEFAULT 'public',
                        sensitivity_class text NOT NULL DEFAULT 'public',
                        license_policy_status text NOT NULL DEFAULT 'allowed',
                        embedding vector(3) NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                text(
                    f"""
                    INSERT INTO {table} (
                        id,
                        sanitized_text,
                        source_allowlisted,
                        access_policy_id,
                        visibility_label,
                        sensitivity_class,
                        license_policy_status,
                        embedding
                    )
                    VALUES
                        (
                            :expected_id,
                            :expected_text,
                            true,
                            'public',
                            'public',
                            'public',
                            'allowed',
                            '[0,0.9,0.1]'::vector
                        ),
                        (
                            :blocked_id,
                            :blocked_text,
                            false,
                            'public',
                            'public',
                            'public',
                            'allowed',
                            '[0,1,0]'::vector
                        ),
                        (
                            :other_id,
                            :other_text,
                            true,
                            'public',
                            'public',
                            'public',
                            'allowed',
                            '[1,0,0]'::vector
                        )
                    """
                ),
                {
                    "expected_id": expected_id,
                    "expected_text": (
                        "Public semantic retrieval smoke test documentation."
                    ),
                    "blocked_id": "blocked-semantic-retrieval",
                    "blocked_text": (
                        "Public semantic retrieval semantic retrieval fixture "
                        "excluded by source policy."
                    ),
                    "other_id": "public-maintenance-notes",
                    "other_text": "Public maintenance notes for index setup.",
                },
            )
            connection.execute(
                text(
                    f"""
                    CREATE INDEX {bm25_index}
                    ON {table}
                    USING bm25 (id, sanitized_text)
                    WITH (key_field='id')
                    """
                )
            )
            connection.execute(
                text(
                    f"""
                    CREATE INDEX {hnsw_index}
                    ON {table}
                    USING hnsw (embedding vector_cosine_ops)
                    """
                )
            )
            connection.execute(text(f"ANALYZE {table}"))

            trigram_similarity = connection.execute(
                text(
                    """
                    SELECT similarity(
                        'semantic retrieval',
                        'semantics retrieval'
                    )
                    """
                )
            ).scalar_one()
            assert trigram_similarity > 0

            bm25_rows = connection.execute(
                text(
                    f"""
                    SELECT id, pdb.score(id) AS bm25_score
                    FROM {table}
                    WHERE {_ACCESS_FILTERS_SQL}
                    AND sanitized_text ||| :query
                    ORDER BY bm25_score DESC, id
                    LIMIT 2
                    """
                ),
                {"query": "semantic retrieval"},
            ).all()
            assert bm25_rows
            assert bm25_rows[0].id == expected_id
            assert bm25_rows[0].bm25_score > 0

            connection.execute(text("SET LOCAL enable_seqscan = off"))
            vector_plan = "\n".join(
                connection.execute(
                    text(
                        f"""
                        EXPLAIN (FORMAT TEXT, COSTS OFF)
                        SELECT id
                        FROM {table}
                        WHERE {_ACCESS_FILTERS_SQL}
                        ORDER BY embedding <=> '[0,1,0]'::vector
                        LIMIT 1
                        """
                    )
                ).scalars()
            )
            assert hnsw_index_name in vector_plan

            vector_id = (
                connection.execute(
                    text(
                        f"""
                        SELECT id
                        FROM {table}
                        WHERE {_ACCESS_FILTERS_SQL}
                        ORDER BY embedding <=> '[0,1,0]'::vector
                        LIMIT 1
                        """
                    )
                )
                .scalars()
                .one()
            )
            assert vector_id == expected_id
    finally:
        if schema_created:
            with engine.begin() as connection:
                connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        engine.dispose()
