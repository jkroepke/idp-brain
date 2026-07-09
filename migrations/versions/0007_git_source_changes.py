"""Add Git source change provenance fields."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_git_source_changes"
down_revision: str | None = "0006_ingestion_run_status_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist sanitized Git commit provenance for source changes."""

    op.add_column(
        "source_changes",
        sa.Column("source_version_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "source_changes",
        sa.Column(
            "parent_shas",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
    )
    op.add_column(
        "source_changes",
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "source_changes",
        sa.Column(
            "source_allowlisted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "source_changes",
        sa.Column(
            "visibility_label",
            sa.String(length=100),
            server_default="invited_users",
            nullable=False,
        ),
    )
    op.add_column(
        "source_changes",
        sa.Column(
            "sensitivity_class",
            sa.String(length=100),
            server_default="unknown",
            nullable=False,
        ),
    )
    op.add_column(
        "source_changes",
        sa.Column(
            "license_policy_status",
            sa.String(length=100),
            server_default="unknown",
            nullable=False,
        ),
    )
    op.add_column(
        "source_changes",
        sa.Column("license_id", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "source_changes",
        sa.Column(
            "redaction_status",
            sa.String(length=100),
            server_default="unknown",
            nullable=False,
        ),
    )
    op.create_foreign_key(
        op.f("fk_source_changes_source_version_id_source_versions"),
        "source_changes",
        "source_versions",
        ["source_version_id"],
        ["id"],
    )
    op.create_check_constraint(
        op.f("ck_source_changes_source_changes_license_policy_status_valid"),
        "source_changes",
        "license_policy_status IN ('unknown', 'review_required', 'allowed', 'denied')",
    )
    op.create_check_constraint(
        op.f("ck_source_changes_source_changes_sensitivity_class_valid"),
        "source_changes",
        "sensitivity_class IN "
        "('unknown', 'public', 'internal', 'confidential', 'restricted')",
    )
    op.create_check_constraint(
        op.f("ck_source_changes_source_changes_visibility_label_valid"),
        "source_changes",
        "visibility_label IN ('invited_users')",
    )
    op.create_check_constraint(
        op.f("ck_source_changes_source_changes_redaction_status_valid"),
        "source_changes",
        "redaction_status IN ('unknown', 'not_required', 'redacted', 'blocked')",
    )
    op.create_check_constraint(
        op.f("ck_source_changes_source_changes_allowed_license_id_valid"),
        "source_changes",
        "license_policy_status != 'allowed' OR license_id IN ('MIT', 'Apache-2.0')",
    )
    op.create_check_constraint(
        op.f("ck_source_changes_source_changes_license_id_presence_valid"),
        "source_changes",
        "license_id IS NOT NULL "
        "OR license_policy_status IN ('unknown', 'review_required')",
    )
    op.create_index(
        op.f("ix_source_changes_filter_pushdown"),
        "source_changes",
        [
            "source_id",
            "source_version_id",
            "source_allowlisted",
            "visibility_label",
            "sensitivity_class",
            "license_policy_status",
            "redaction_status",
        ],
    )
    op.create_index(
        op.f("ix_source_changes_license_id"),
        "source_changes",
        ["license_id"],
    )
    op.alter_column("source_changes", "parent_shas", server_default=None)
    op.alter_column("source_changes", "source_allowlisted", server_default=None)
    op.alter_column("source_changes", "visibility_label", server_default=None)
    op.alter_column("source_changes", "sensitivity_class", server_default=None)
    op.alter_column("source_changes", "license_policy_status", server_default=None)
    op.alter_column("source_changes", "redaction_status", server_default=None)


def downgrade() -> None:
    """Remove Git source change provenance fields."""

    op.drop_index(op.f("ix_source_changes_license_id"), "source_changes")
    op.drop_index(op.f("ix_source_changes_filter_pushdown"), "source_changes")
    for suffix in (
        "license_id_presence_valid",
        "allowed_license_id_valid",
        "redaction_status_valid",
        "visibility_label_valid",
        "sensitivity_class_valid",
        "license_policy_status_valid",
    ):
        op.drop_constraint(
            op.f(f"ck_source_changes_source_changes_{suffix}"),
            "source_changes",
            type_="check",
        )
    op.drop_constraint(
        op.f("fk_source_changes_source_version_id_source_versions"),
        "source_changes",
        type_="foreignkey",
    )
    op.drop_column("source_changes", "redaction_status")
    op.drop_column("source_changes", "license_id")
    op.drop_column("source_changes", "license_policy_status")
    op.drop_column("source_changes", "sensitivity_class")
    op.drop_column("source_changes", "visibility_label")
    op.drop_column("source_changes", "source_allowlisted")
    op.drop_column("source_changes", "committed_at")
    op.drop_column("source_changes", "parent_shas")
    op.drop_column("source_changes", "source_version_id")
