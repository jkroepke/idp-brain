"""Add redaction, license, and sanitized retrieval event tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_redaction_license_events"
down_revision: str | None = "0003_corpus_eligibility_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def pk(table_name: str) -> sa.PrimaryKeyConstraint:
    return sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_name}"))


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    """Create sanitized policy and retrieval event tables."""

    op.create_table(
        "redaction_events",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "ingestion_run_id",
            sa.String(length=255),
            sa.ForeignKey(
                "ingestion_runs.id",
                name=op.f("fk_redaction_events_ingestion_run_id_ingestion_runs"),
            ),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.String(length=255),
            sa.ForeignKey(
                "sources.id",
                name=op.f("fk_redaction_events_source_id_sources"),
            ),
            nullable=False,
        ),
        sa.Column(
            "source_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f("fk_redaction_events_source_version_id_source_versions"),
            ),
            nullable=True,
        ),
        sa.Column(
            "artifact_id",
            sa.String(length=255),
            sa.ForeignKey(
                "artifacts.id",
                name=op.f("fk_redaction_events_artifact_id_artifacts"),
            ),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            sa.String(length=255),
            sa.ForeignKey(
                "chunks.id", name=op.f("fk_redaction_events_chunk_id_chunks")
            ),
            nullable=True,
        ),
        sa.Column(
            "citation_id",
            sa.String(length=255),
            sa.ForeignKey(
                "citations.id",
                name=op.f("fk_redaction_events_citation_id_citations"),
            ),
            nullable=True,
        ),
        sa.Column("detector_name", sa.String(length=255), nullable=False),
        sa.Column("detector_version", sa.String(length=255), nullable=True),
        sa.Column("rule_id", sa.String(length=255), nullable=True),
        sa.Column("marker", sa.String(length=255), nullable=False),
        sa.Column("match_count", sa.Integer(), nullable=False),
        sa.Column("location_locator", sa.String(length=2048), nullable=True),
        sa.Column("sanitized_content_hash", sa.String(length=255), nullable=True),
        sa.Column("redaction_profile", sa.String(length=255), nullable=False),
        sa.Column(
            "severity",
            sa.String(length=100),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column(
            "redaction_status",
            sa.String(length=100),
            server_default="redacted",
            nullable=False,
        ),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        *timestamp_columns(),
        pk("redaction_events"),
        sa.CheckConstraint(
            "match_count >= 0",
            name=op.f("ck_redaction_events_match_count_non_negative"),
        ),
        sa.CheckConstraint(
            "severity IN ('unknown', 'low', 'medium', 'high', 'critical')",
            name=op.f("ck_redaction_events_severity_valid"),
        ),
        sa.CheckConstraint(
            "redaction_status IN ('unknown', 'not_required', 'redacted', 'blocked')",
            name=op.f("ck_redaction_events_redaction_status_valid"),
        ),
    )
    op.create_index(
        op.f("ix_redaction_events_ingestion_run_id"),
        "redaction_events",
        ["ingestion_run_id"],
    )
    op.create_index(
        op.f("ix_redaction_events_source_version_artifact"),
        "redaction_events",
        ["source_id", "source_version_id", "artifact_id"],
    )
    op.create_index(
        op.f("ix_redaction_events_chunk_id"),
        "redaction_events",
        ["chunk_id"],
    )
    op.create_index(
        op.f("ix_redaction_events_citation_id"),
        "redaction_events",
        ["citation_id"],
    )
    op.create_index(
        op.f("ix_redaction_events_sanitized_content_hash"),
        "redaction_events",
        ["sanitized_content_hash"],
    )

    op.create_table(
        "license_findings",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "source_id",
            sa.String(length=255),
            sa.ForeignKey(
                "sources.id",
                name=op.f("fk_license_findings_source_id_sources"),
            ),
            nullable=False,
        ),
        sa.Column(
            "source_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f("fk_license_findings_source_version_id_source_versions"),
            ),
            nullable=True,
        ),
        sa.Column(
            "artifact_id",
            sa.String(length=255),
            sa.ForeignKey(
                "artifacts.id",
                name=op.f("fk_license_findings_artifact_id_artifacts"),
            ),
            nullable=False,
        ),
        sa.Column(
            "citation_id",
            sa.String(length=255),
            sa.ForeignKey(
                "citations.id",
                name=op.f("fk_license_findings_citation_id_citations"),
            ),
            nullable=True,
        ),
        sa.Column("scanner_name", sa.String(length=255), nullable=False),
        sa.Column("scanner_version", sa.String(length=255), nullable=True),
        sa.Column("license_expression", sa.String(length=1024), nullable=True),
        sa.Column("license_id", sa.String(length=100), nullable=True),
        sa.Column("copyright_notice", sa.Text(), nullable=True),
        sa.Column("finding_location", sa.String(length=2048), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "policy_status",
            sa.String(length=100),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        *timestamp_columns(),
        pk("license_findings"),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name=op.f("ck_license_findings_confidence_range"),
        ),
        sa.CheckConstraint(
            "policy_status IN ('unknown', 'review_required', 'allowed', 'denied')",
            name=op.f("ck_license_findings_policy_status_valid"),
        ),
    )
    op.create_index(
        op.f("ix_license_findings_source_version_artifact"),
        "license_findings",
        ["source_id", "source_version_id", "artifact_id"],
    )
    op.create_index(
        op.f("ix_license_findings_policy_status"),
        "license_findings",
        ["policy_status"],
    )
    op.create_index(
        op.f("ix_license_findings_license_id"),
        "license_findings",
        ["license_id"],
    )
    op.create_index(
        op.f("ix_license_findings_citation_id"),
        "license_findings",
        ["citation_id"],
    )

    op.create_table(
        "retrieval_events",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "ingestion_run_id",
            sa.String(length=255),
            sa.ForeignKey(
                "ingestion_runs.id",
                name=op.f("fk_retrieval_events_ingestion_run_id_ingestion_runs"),
            ),
            nullable=True,
        ),
        sa.Column(
            "source_id",
            sa.String(length=255),
            sa.ForeignKey(
                "sources.id", name=op.f("fk_retrieval_events_source_id_sources")
            ),
            nullable=True,
        ),
        sa.Column(
            "source_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f("fk_retrieval_events_source_version_id_source_versions"),
            ),
            nullable=True,
        ),
        sa.Column("query_hash", sa.String(length=255), nullable=False),
        sa.Column("sanitized_query_preview", sa.String(length=512), nullable=True),
        sa.Column(
            "query_token_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("trusted_filters", sa.JSON(), nullable=False),
        sa.Column("selected_ids", sa.JSON(), nullable=False),
        sa.Column(
            "primary_selected_chunk_id",
            sa.String(length=255),
            sa.ForeignKey(
                "chunks.id",
                name=op.f("fk_retrieval_events_primary_selected_chunk_id_chunks"),
            ),
            nullable=True,
        ),
        sa.Column(
            "primary_selected_citation_id",
            sa.String(length=255),
            sa.ForeignKey(
                "citations.id",
                name=op.f("fk_retrieval_events_primary_selected_citation_id_citations"),
            ),
            nullable=True,
        ),
        sa.Column(
            "primary_selected_artifact_id",
            sa.String(length=255),
            sa.ForeignKey(
                "artifacts.id",
                name=op.f("fk_retrieval_events_primary_selected_artifact_id_artifacts"),
            ),
            nullable=True,
        ),
        sa.Column("selected_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("selected_citation_ids", sa.JSON(), nullable=False),
        sa.Column("selected_artifact_ids", sa.JSON(), nullable=False),
        sa.Column("ranking_diagnostics", sa.JSON(), nullable=False),
        sa.Column(
            "redaction_status",
            sa.String(length=100),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column(
            "corpus_eligibility_filter_result",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column("active_index_version_id", sa.String(length=255), nullable=True),
        sa.Column(
            "searched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        *timestamp_columns(),
        pk("retrieval_events"),
        sa.CheckConstraint(
            "query_token_count >= 0",
            name=op.f("ck_retrieval_events_query_token_count_non_negative"),
        ),
        sa.CheckConstraint(
            "redaction_status IN ('unknown', 'not_required', 'redacted', 'blocked')",
            name=op.f("ck_retrieval_events_redaction_status_valid"),
        ),
        sa.CheckConstraint(
            "corpus_eligibility_filter_result IN "
            "('allowed', 'blocked', 'partial', 'diagnostic_only')",
            name=op.f("ck_retrieval_events_corpus_eligibility_filter_result_valid"),
        ),
    )
    op.create_index(
        op.f("ix_retrieval_events_query_hash"),
        "retrieval_events",
        ["query_hash"],
    )
    op.create_index(
        op.f("ix_retrieval_events_ingestion_run_id"),
        "retrieval_events",
        ["ingestion_run_id"],
    )
    op.create_index(
        op.f("ix_retrieval_events_source_id"),
        "retrieval_events",
        ["source_id"],
    )
    op.create_index(
        op.f("ix_retrieval_events_primary_selected_chunk_id"),
        "retrieval_events",
        ["primary_selected_chunk_id"],
    )
    op.create_index(
        op.f("ix_retrieval_events_primary_selected_citation_id"),
        "retrieval_events",
        ["primary_selected_citation_id"],
    )
    op.create_index(
        op.f("ix_retrieval_events_primary_selected_artifact_id"),
        "retrieval_events",
        ["primary_selected_artifact_id"],
    )
    op.create_index(
        op.f("ix_retrieval_events_active_index_version_id"),
        "retrieval_events",
        ["active_index_version_id"],
    )
    op.create_index(
        op.f("ix_retrieval_events_filter_result"),
        "retrieval_events",
        ["corpus_eligibility_filter_result", "redaction_status"],
    )


def downgrade() -> None:
    """Drop sanitized policy and retrieval event tables."""

    for index_name in (
        "ix_retrieval_events_filter_result",
        "ix_retrieval_events_active_index_version_id",
        "ix_retrieval_events_primary_selected_artifact_id",
        "ix_retrieval_events_primary_selected_citation_id",
        "ix_retrieval_events_primary_selected_chunk_id",
        "ix_retrieval_events_source_id",
        "ix_retrieval_events_ingestion_run_id",
        "ix_retrieval_events_query_hash",
    ):
        op.drop_index(op.f(index_name), "retrieval_events")
    op.drop_table("retrieval_events")

    for index_name in (
        "ix_license_findings_citation_id",
        "ix_license_findings_license_id",
        "ix_license_findings_policy_status",
        "ix_license_findings_source_version_artifact",
    ):
        op.drop_index(op.f(index_name), "license_findings")
    op.drop_table("license_findings")

    for index_name in (
        "ix_redaction_events_sanitized_content_hash",
        "ix_redaction_events_citation_id",
        "ix_redaction_events_chunk_id",
        "ix_redaction_events_source_version_artifact",
        "ix_redaction_events_ingestion_run_id",
    ):
        op.drop_index(op.f(index_name), "redaction_events")
    op.drop_table("redaction_events")
