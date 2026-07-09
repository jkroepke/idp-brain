"""Persist chunk structure and citation corpus provenance."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_chunk_citation_provenance"
down_revision: str | None = "0009_redaction_policy_labels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add safe chunk structure metadata and corpus labels."""

    op.add_column(
        "chunks",
        sa.Column(
            "structure_path",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )
    op.add_column(
        "chunks",
        sa.Column(
            "corpus_eligibility_label",
            sa.String(length=255),
            server_default="unknown",
            nullable=False,
        ),
    )
    op.add_column(
        "chunks",
        sa.Column(
            "metadata",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.add_column(
        "citations",
        sa.Column(
            "corpus_eligibility_label",
            sa.String(length=255),
            server_default="unknown",
            nullable=False,
        ),
    )

    op.alter_column("chunks", "structure_path", server_default=None)
    op.alter_column("chunks", "corpus_eligibility_label", server_default=None)
    op.alter_column("chunks", "metadata", server_default=None)
    op.alter_column("citations", "corpus_eligibility_label", server_default=None)


def downgrade() -> None:
    """Remove safe chunk structure metadata and corpus labels."""

    op.drop_column("citations", "corpus_eligibility_label")
    op.drop_column("chunks", "metadata")
    op.drop_column("chunks", "corpus_eligibility_label")
    op.drop_column("chunks", "structure_path")
