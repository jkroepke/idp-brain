import pytest
from sqlalchemy import text

from idp_brain.db import create_db_engine


@pytest.mark.integration
def test_required_extensions_are_enabled_by_migration() -> None:
    engine = create_db_engine()

    with engine.connect() as connection:
        extension_names = connection.execute(
            text(
                """
                SELECT extname
                FROM pg_extension
                WHERE extname IN ('vector', 'pg_search', 'pg_trgm')
                ORDER BY extname
                """
            )
        ).scalars()

        assert list(extension_names) == ["pg_search", "pg_trgm", "vector"]
