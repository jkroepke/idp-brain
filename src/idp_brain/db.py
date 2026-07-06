"""Database engine and session helpers."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from idp_brain.settings import Settings, load_settings


def create_db_engine(settings: Settings | None = None) -> Engine:
    """Create a SQLAlchemy engine from application settings."""

    current_settings = settings or load_settings()
    return create_engine(current_settings.database_url, future=True)


def create_session_factory(
    engine: Engine | None = None,
    settings: Settings | None = None,
) -> sessionmaker[Session]:
    """Create a session factory bound to an engine."""

    current_engine = engine or create_db_engine(settings)
    return sessionmaker(bind=current_engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(
    session_factory: sessionmaker[Session] | None = None,
) -> Iterator[Session]:
    """Yield a session and close it after use."""

    current_session_factory = session_factory or create_session_factory()
    with current_session_factory() as session:
        yield session
