"""Add corpus eligibility metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_corpus_eligibility_metadata"
down_revision: str | None = "0002_core_data_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_ALLOWLISTED = sa.Column(
    "source_allowlisted",
    sa.Boolean(),
    server_default=sa.text("false"),
    nullable=False,
)
LICENSE_POLICY_STATUS = sa.Column(
    "license_policy_status",
    sa.String(length=100),
    server_default="unknown",
    nullable=False,
)
LICENSE_ID = sa.Column("license_id", sa.String(length=100), nullable=True)
VISIBILITY_LABEL = sa.Column(
    "visibility_label",
    sa.String(length=100),
    server_default="invited_users",
    nullable=False,
)
SENSITIVITY_CLASS = sa.Column(
    "sensitivity_class",
    sa.String(length=100),
    server_default="unknown",
    nullable=False,
)
REDACTION_STATUS = sa.Column(
    "redaction_status",
    sa.String(length=100),
    server_default="unknown",
    nullable=False,
)

ELIGIBILITY_COLUMNS = (
    "source_allowlisted",
    "visibility_label",
    "sensitivity_class",
    "license_policy_status",
    "redaction_status",
)
PROVENANCE_TABLES = (
    "artifacts",
    "chunks",
    "citations",
    "facts",
    "claims",
    "relationships",
)
ELIGIBILITY_TABLES = ("sources", "source_versions", *PROVENANCE_TABLES)


def _copy_column(column: sa.Column) -> sa.Column:
    return column.copy()


def _create_eligibility_constraints(table_name: str) -> None:
    op.create_check_constraint(
        op.f(f"ck_{table_name}_{table_name}_license_policy_status_valid"),
        table_name,
        "license_policy_status IN ('unknown', 'review_required', 'allowed', 'denied')",
    )
    op.create_check_constraint(
        op.f(f"ck_{table_name}_{table_name}_sensitivity_class_valid"),
        table_name,
        "sensitivity_class IN "
        "('unknown', 'public', 'internal', 'confidential', 'restricted')",
    )
    op.create_check_constraint(
        op.f(f"ck_{table_name}_{table_name}_visibility_label_valid"),
        table_name,
        "visibility_label IN ('invited_users')",
    )
    op.create_check_constraint(
        op.f(f"ck_{table_name}_{table_name}_redaction_status_valid"),
        table_name,
        "redaction_status IN ('unknown', 'not_required', 'redacted', 'blocked')",
    )
    op.create_check_constraint(
        op.f(f"ck_{table_name}_{table_name}_allowed_license_id_valid"),
        table_name,
        "license_policy_status != 'allowed' OR license_id IN ('MIT', 'Apache-2.0')",
    )
    op.create_check_constraint(
        op.f(f"ck_{table_name}_{table_name}_license_id_presence_valid"),
        table_name,
        "license_id IS NOT NULL "
        "OR license_policy_status IN ('unknown', 'review_required')",
    )


def _drop_eligibility_constraints(table_name: str) -> None:
    for suffix in (
        "license_id_presence_valid",
        "allowed_license_id_valid",
        "redaction_status_valid",
        "visibility_label_valid",
        "sensitivity_class_valid",
        "license_policy_status_valid",
    ):
        op.drop_constraint(
            op.f(f"ck_{table_name}_{table_name}_{suffix}"),
            table_name,
            type_="check",
        )


def _create_filter_index(table_name: str, *columns: str) -> None:
    op.create_index(
        op.f(f"ix_{table_name}_filter_pushdown"),
        table_name,
        [*columns],
    )


def upgrade() -> None:
    """Add global corpus eligibility policy metadata."""

    op.create_table(
        "corpus_policy_defaults",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("policy_version", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "source_allowlist_default",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "allowed_license_ids",
            sa.JSON(),
            server_default=sa.text("""'["MIT", "Apache-2.0"]'"""),
            nullable=False,
        ),
        sa.Column(
            "allowed_license_policy_statuses",
            sa.JSON(),
            server_default=sa.text("""'["allowed"]'"""),
            nullable=False,
        ),
        sa.Column(
            "allowed_sensitivity_classes",
            sa.JSON(),
            server_default=sa.text("""'["public"]'"""),
            nullable=False,
        ),
        sa.Column(
            "allowed_visibility_labels",
            sa.JSON(),
            server_default=sa.text("""'["invited_users"]'"""),
            nullable=False,
        ),
        sa.Column(
            "allowed_redaction_statuses",
            sa.JSON(),
            server_default=sa.text("""'["not_required", "redacted"]'"""),
            nullable=False,
        ),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_corpus_policy_defaults")),
        sa.CheckConstraint(
            "source_allowlist_default = false",
            name=op.f("ck_corpus_policy_defaults_source_allowlist_default_fail_closed"),
        ),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO corpus_policy_defaults (
                id,
                policy_version,
                description,
                source_allowlist_default,
                allowed_license_ids,
                allowed_license_policy_statuses,
                allowed_sensitivity_classes,
                allowed_visibility_labels,
                allowed_redaction_statuses
            )
            VALUES (
                'global',
                'mvp-2.4',
                'MVP global corpus eligibility defaults.',
                false,
                '["MIT", "Apache-2.0"]',
                '["allowed"]',
                '["public"]',
                '["invited_users"]',
                '["not_required", "redacted"]'
            )
            """
        )
    )

    op.add_column("sources", _copy_column(SOURCE_ALLOWLISTED))
    op.add_column("sources", _copy_column(LICENSE_POLICY_STATUS))
    op.add_column("sources", _copy_column(LICENSE_ID))
    op.add_column("sources", _copy_column(REDACTION_STATUS))
    op.alter_column("sources", "visibility_label", server_default="invited_users")
    op.execute("UPDATE sources SET visibility_label = 'invited_users'")

    for table_name in PROVENANCE_TABLES:
        op.add_column(table_name, _copy_column(SOURCE_ALLOWLISTED))
        op.add_column(table_name, _copy_column(LICENSE_POLICY_STATUS))
        op.add_column(table_name, _copy_column(LICENSE_ID))
        op.alter_column(table_name, "visibility_label", server_default="invited_users")
        op.alter_column(table_name, "redaction_status", server_default="unknown")
        op.execute(f"UPDATE {table_name} SET visibility_label = 'invited_users'")
        op.execute(f"UPDATE {table_name} SET redaction_status = 'unknown'")

    for column in (
        SOURCE_ALLOWLISTED,
        VISIBILITY_LABEL,
        SENSITIVITY_CLASS,
        LICENSE_POLICY_STATUS,
        LICENSE_ID,
        REDACTION_STATUS,
    ):
        op.add_column("source_versions", _copy_column(column))

    for table_name in ELIGIBILITY_TABLES:
        _create_eligibility_constraints(table_name)
        op.create_index(
            op.f(f"ix_{table_name}_license_id"),
            table_name,
            ["license_id"],
        )

    _create_filter_index(
        "sources",
        "source_allowlisted",
        "visibility_label",
        "sensitivity_class",
        "license_policy_status",
        "redaction_status",
    )
    _create_filter_index(
        "source_versions",
        "source_id",
        "version_label",
        "source_allowlisted",
        "visibility_label",
        "sensitivity_class",
        "license_policy_status",
        "redaction_status",
        "is_current",
    )
    _create_filter_index(
        "artifacts",
        "source_id",
        "source_version_id",
        "source_allowlisted",
        "visibility_label",
        "sensitivity_class",
        "license_policy_status",
        "redaction_status",
        "path",
        "language",
        "version_label",
    )
    _create_filter_index(
        "chunks",
        "source_id",
        "source_version_id",
        "source_allowlisted",
        "visibility_label",
        "sensitivity_class",
        "license_policy_status",
        "redaction_status",
        "artifact_path",
        "language",
        "version_label",
    )
    _create_filter_index(
        "citations",
        "source_id",
        "source_version_id",
        "source_allowlisted",
        "visibility_label",
        "sensitivity_class",
        "license_policy_status",
        "redaction_status",
        "version_label",
    )
    _create_filter_index(
        "facts",
        "source_id",
        "source_version_id",
        "source_allowlisted",
        "visibility_label",
        "sensitivity_class",
        "license_policy_status",
        "redaction_status",
        "version_label",
    )
    _create_filter_index(
        "claims",
        "source_id",
        "source_version_id",
        "source_allowlisted",
        "visibility_label",
        "sensitivity_class",
        "license_policy_status",
        "redaction_status",
        "version_label",
    )
    _create_filter_index(
        "relationships",
        "source_id",
        "source_version_id",
        "source_allowlisted",
        "visibility_label",
        "sensitivity_class",
        "license_policy_status",
        "redaction_status",
        "version_label",
    )

    op.create_index(
        op.f("ix_citations_chunk_id"),
        "citations",
        ["chunk_id"],
    )
    for table_name in ("facts", "claims", "relationships"):
        op.create_index(
            op.f(f"ix_{table_name}_primary_citation_id"),
            table_name,
            ["primary_citation_id"],
        )
    for table_name, id_column in (
        ("artifact_versions", "artifact_id"),
        ("chunk_versions", "chunk_id"),
        ("fact_versions", "fact_id"),
        ("claim_versions", "claim_id"),
        ("relationship_versions", "relationship_id"),
    ):
        op.create_index(
            op.f(f"ix_{table_name}_active_version_filter"),
            table_name,
            [id_column, "source_version_id", "version_label", "is_current"],
        )


def downgrade() -> None:
    """Remove global corpus eligibility policy metadata."""

    for table_name in (
        "relationship_versions",
        "claim_versions",
        "fact_versions",
        "chunk_versions",
        "artifact_versions",
    ):
        op.drop_index(op.f(f"ix_{table_name}_active_version_filter"), table_name)

    for table_name in ("facts", "claims", "relationships"):
        op.drop_index(op.f(f"ix_{table_name}_primary_citation_id"), table_name)
    op.drop_index(op.f("ix_citations_chunk_id"), "citations")

    for table_name in ELIGIBILITY_TABLES:
        op.drop_index(op.f(f"ix_{table_name}_filter_pushdown"), table_name)
        op.drop_index(op.f(f"ix_{table_name}_license_id"), table_name)
        _drop_eligibility_constraints(table_name)

    for table_name in PROVENANCE_TABLES:
        op.alter_column(table_name, "redaction_status", server_default="not_redacted")
        op.alter_column(table_name, "visibility_label", server_default="public")
        op.drop_column(table_name, "license_id")
        op.drop_column(table_name, "license_policy_status")
        op.drop_column(table_name, "source_allowlisted")

    for column_name in (
        "redaction_status",
        "license_id",
        "license_policy_status",
        "sensitivity_class",
        "visibility_label",
        "source_allowlisted",
    ):
        op.drop_column("source_versions", column_name)

    op.drop_column("sources", "redaction_status")
    op.drop_column("sources", "license_id")
    op.drop_column("sources", "license_policy_status")
    op.drop_column("sources", "source_allowlisted")
    op.alter_column("sources", "visibility_label", server_default="public")

    op.drop_table("corpus_policy_defaults")
