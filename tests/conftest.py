from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine

from idp_brain.settings import Settings


def _database_url() -> str:
    return os.environ.get("IDP_BRAIN_DATABASE_URL", Settings().database_url)


@pytest.fixture
def alembic_config() -> Config:
    return Config("alembic.ini")


@pytest.fixture
def phase2_migrated_engine(alembic_config: Config) -> Iterator[Engine]:
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

    engine = create_engine(_database_url(), future=True)
    try:
        yield engine
    finally:
        engine.dispose()
