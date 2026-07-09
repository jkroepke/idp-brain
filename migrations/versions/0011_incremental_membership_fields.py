"""Add incremental tombstone metadata to version memberships."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_incremental_membership"
down_revision: str | None = "0010_chunk_citation_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VERSION_TABLES: tuple[str, ...] = (
    "artifact_versions",
    "chunk_versions",
    "fact_versions",
    "claim_versions",
    "relationship_versions",
)


def upgrade() -> None:
    """Add explicit tombstone metadata for historical memberships."""

    for table_name in VERSION_TABLES:
        op.add_column(
            table_name,
            sa.Column("tombstoned_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.add_column(
            table_name,
            sa.Column("tombstone_reason", sa.String(length=255), nullable=True),
        )


def downgrade() -> None:
    """Remove explicit tombstone metadata for historical memberships."""

    for table_name in reversed(VERSION_TABLES):
        op.drop_column(table_name, "tombstone_reason")
        op.drop_column(table_name, "tombstoned_at")
