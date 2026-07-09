"""Add redaction and license policy event labels."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_redaction_policy_labels"
down_revision: str | None = "0008_artifact_corpus_eligibility"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist safe policy labels on redaction and license findings."""

    op.add_column(
        "redaction_events",
        sa.Column(
            "redaction_type",
            sa.String(length=100),
            server_default="secret",
            nullable=False,
        ),
    )
    op.add_column(
        "redaction_events", sa.Column("confidence", sa.Float(), nullable=True)
    )
    _add_policy_label_columns("redaction_events")

    _add_policy_label_columns("license_findings")

    op.alter_column("redaction_events", "redaction_type", server_default=None)
    for table_name in ("redaction_events", "license_findings"):
        op.alter_column(table_name, "corpus_eligibility_label", server_default=None)
        op.alter_column(table_name, "visibility_label", server_default=None)
        op.alter_column(table_name, "sensitivity_class", server_default=None)
        op.alter_column(table_name, "license_policy_label", server_default=None)


def downgrade() -> None:
    """Remove safe policy labels from redaction and license findings."""

    for table_name in ("license_findings", "redaction_events"):
        op.drop_column(table_name, "license_policy_label")
        op.drop_column(table_name, "sensitivity_class")
        op.drop_column(table_name, "visibility_label")
        op.drop_column(table_name, "corpus_eligibility_label")
    op.drop_column("redaction_events", "confidence")
    op.drop_column("redaction_events", "redaction_type")


def _add_policy_label_columns(table_name: str) -> None:
    op.add_column(
        table_name,
        sa.Column(
            "corpus_eligibility_label",
            sa.String(length=255),
            server_default="unknown",
            nullable=False,
        ),
    )
    op.add_column(
        table_name,
        sa.Column(
            "visibility_label",
            sa.String(length=100),
            server_default="invited_users",
            nullable=False,
        ),
    )
    op.add_column(
        table_name,
        sa.Column(
            "sensitivity_class",
            sa.String(length=100),
            server_default="unknown",
            nullable=False,
        ),
    )
    op.add_column(
        table_name,
        sa.Column(
            "license_policy_label",
            sa.String(length=100),
            server_default="unknown",
            nullable=False,
        ),
    )
