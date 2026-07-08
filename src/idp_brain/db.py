"""Database engine and session helpers."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from idp_brain.settings import Settings, load_settings

REQUIRED_EXTENSIONS = frozenset({"pg_search", "pg_trgm", "vector"})
PHASE_2_TABLES = frozenset(
    {
        "alembic_version",
        "artifacts",
        "artifact_extractions",
        "artifact_versions",
        "change_versions",
        "chunks",
        "chunk_versions",
        "citations",
        "claim_conflicts",
        "claims",
        "claim_versions",
        "corpus_policy_defaults",
        "embeddings",
        "embedding_jobs",
        "embedding_models",
        "facts",
        "fact_versions",
        "index_versions",
        "ingestion_runs",
        "license_findings",
        "redaction_events",
        "relationships",
        "relationship_versions",
        "retrieval_events",
        "source_changes",
        "source_versions",
        "sources",
    }
)

LOCAL_RESET_HOSTS = frozenset({"localhost", "127.0.0.1"})
LOCAL_RESET_PORTS = frozenset({55432})
LOCAL_RESET_DATABASES = frozenset({"idp_brain"})
LOCAL_RESET_USERS = frozenset({"idp_brain"})


@dataclass(frozen=True)
class SchemaCheckResult:
    """Outcome of a deterministic local schema check."""

    extensions: tuple[str, ...]
    tables: tuple[str, ...]
    missing_extensions: tuple[str, ...]
    missing_tables: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Return true when all required schema objects are present."""

        return not self.missing_extensions and not self.missing_tables


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


def check_schema(engine: Engine | None = None) -> SchemaCheckResult:
    """Check that the local database contains required Phase 2 schema objects."""

    current_engine = engine or create_db_engine()
    with current_engine.connect() as connection:
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
        tables = set(inspect(connection).get_table_names(schema="public"))

    missing_extensions = tuple(sorted(REQUIRED_EXTENSIONS - extensions))
    missing_tables = tuple(sorted(PHASE_2_TABLES - tables))

    return SchemaCheckResult(
        extensions=tuple(sorted(extensions)),
        tables=tuple(sorted(tables)),
        missing_extensions=missing_extensions,
        missing_tables=missing_tables,
    )


def is_local_reset_database_url(database_url: str) -> bool:
    """Return true only for the disposable Docker Compose database URL."""

    parsed = urlparse(database_url)
    return (
        parsed.hostname in LOCAL_RESET_HOSTS
        and (parsed.port or 5432) in LOCAL_RESET_PORTS
        and parsed.path.lstrip("/") in LOCAL_RESET_DATABASES
        and (parsed.username or "") in LOCAL_RESET_USERS
    )
