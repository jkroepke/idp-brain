"""Enable required PostgreSQL extensions."""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_enable_extensions"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable extensions required by the local retrieval store."""

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_search")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    """Leave shared local extensions installed on downgrade."""

    # Local extension removal can affect other disposable schemas/databases in
    # the same development instance, so downgrade intentionally does nothing.
    pass
