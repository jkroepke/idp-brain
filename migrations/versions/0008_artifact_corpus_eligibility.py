"""Add artifact corpus eligibility metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_artifact_corpus_eligibility"
down_revision: str | None = "0007_git_source_changes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Carry configured corpus eligibility onto artifact metadata."""

    op.add_column(
        "artifacts",
        sa.Column(
            "corpus_eligibility_label",
            sa.String(length=255),
            server_default="unknown",
            nullable=False,
        ),
    )
    op.alter_column("artifacts", "corpus_eligibility_label", server_default=None)


def downgrade() -> None:
    """Remove artifact corpus eligibility metadata."""

    op.drop_column("artifacts", "corpus_eligibility_label")
