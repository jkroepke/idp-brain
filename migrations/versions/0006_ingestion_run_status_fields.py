"""Add ingestion run lifecycle metadata fields."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_ingestion_run_status_fields"
down_revision: str | None = "0005_index_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add config-derived run metadata, counters, and sanitized diagnostics."""

    op.add_column(
        "ingestion_runs", sa.Column("config_source_id", sa.String(length=255))
    )
    op.add_column("ingestion_runs", sa.Column("config_file_hash", sa.String(length=64)))
    op.add_column("ingestion_runs", sa.Column("operator_label", sa.String(length=255)))
    op.add_column(
        "ingestion_runs", sa.Column("extractor_profile", sa.String(length=255))
    )
    op.add_column(
        "ingestion_runs", sa.Column("visibility_label", sa.String(length=100))
    )
    op.add_column(
        "ingestion_runs", sa.Column("sensitivity_class", sa.String(length=100))
    )
    op.add_column(
        "ingestion_runs", sa.Column("license_policy_status", sa.String(length=100))
    )
    op.add_column(
        "ingestion_runs",
        sa.Column("corpus_eligibility_label", sa.String(length=255)),
    )
    op.add_column(
        "ingestion_runs",
        sa.Column(
            "diagnostics",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
    )
    op.alter_column("ingestion_runs", "diagnostics", server_default=None)
    op.create_index(
        op.f("ix_ingestion_runs_config_source_status"),
        "ingestion_runs",
        ["config_source_id", "status"],
    )


def downgrade() -> None:
    """Remove ingestion run lifecycle metadata fields."""

    op.drop_index(op.f("ix_ingestion_runs_config_source_status"), "ingestion_runs")
    op.drop_column("ingestion_runs", "diagnostics")
    op.drop_column("ingestion_runs", "corpus_eligibility_label")
    op.drop_column("ingestion_runs", "license_policy_status")
    op.drop_column("ingestion_runs", "sensitivity_class")
    op.drop_column("ingestion_runs", "visibility_label")
    op.drop_column("ingestion_runs", "extractor_profile")
    op.drop_column("ingestion_runs", "operator_label")
    op.drop_column("ingestion_runs", "config_file_hash")
    op.drop_column("ingestion_runs", "config_source_id")
