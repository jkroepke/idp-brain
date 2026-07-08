from __future__ import annotations

import pytest
from sqlalchemy import Engine, inspect, text

from idp_brain.db import PHASE_2_TABLES, REQUIRED_EXTENSIONS, check_schema

pytestmark = pytest.mark.integration


def test_alembic_rebuilds_phase_2_schema_from_base(
    phase2_migrated_engine: Engine,
) -> None:
    inspector = inspect(phase2_migrated_engine)
    assert PHASE_2_TABLES <= set(inspector.get_table_names(schema="public"))

    with phase2_migrated_engine.connect() as connection:
        extensions = set(
            connection.execute(
                text(
                    """
                    SELECT extname
                    FROM pg_extension
                    WHERE extname IN ('pg_search', 'pg_trgm', 'vector')
                    """
                )
            ).scalars()
        )
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    assert REQUIRED_EXTENSIONS <= extensions
    assert revision == "0011_incremental_membership"


def test_schema_check_accepts_rebuilt_phase_2_database(
    phase2_migrated_engine: Engine,
) -> None:
    result = check_schema(phase2_migrated_engine)

    assert result.passed
    assert not result.missing_extensions
    assert not result.missing_tables
