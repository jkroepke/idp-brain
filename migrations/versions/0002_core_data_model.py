"""Add core source-backed data model."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_core_data_model"
down_revision: str | None = "0001_enable_extensions"
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


def provenance_columns(table_name: str) -> list[sa.Column]:
    return [
        sa.Column(
            "source_id",
            sa.String(length=255),
            sa.ForeignKey(
                "sources.id", name=op.f(f"fk_{table_name}_source_id_sources")
            ),
            nullable=False,
        ),
        sa.Column(
            "source_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f(f"fk_{table_name}_source_version_id_source_versions"),
            ),
            nullable=True,
        ),
        sa.Column("repository_url", sa.String(length=2048), nullable=True),
        sa.Column("artifact_url", sa.String(length=2048), nullable=True),
        sa.Column("commit_sha", sa.String(length=128), nullable=True),
        sa.Column("tag", sa.String(length=255), nullable=True),
        sa.Column("version", sa.String(length=255), nullable=True),
        sa.Column("version_label", sa.String(length=255), nullable=True),
        sa.Column("checksum", sa.String(length=255), nullable=True),
        sa.Column(
            "first_containing_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f(
                    f"fk_{table_name}_first_containing_version_id_source_versions"
                ),
            ),
            nullable=True,
        ),
        sa.Column(
            "last_containing_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f(
                    f"fk_{table_name}_last_containing_version_id_source_versions"
                ),
            ),
            nullable=True,
        ),
        sa.Column("path", sa.String(length=2048), nullable=True),
        sa.Column("logical_locator", sa.String(length=2048), nullable=True),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("extractor_name", sa.String(length=255), nullable=True),
        sa.Column("extractor_version", sa.String(length=255), nullable=True),
        sa.Column("extractor_profile", sa.String(length=255), nullable=True),
        sa.Column(
            "visibility_label",
            sa.String(length=100),
            server_default="public",
            nullable=False,
        ),
        sa.Column(
            "sensitivity_class",
            sa.String(length=100),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column(
            "redaction_status",
            sa.String(length=100),
            server_default="not_redacted",
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
    ]


def version_lineage_columns(prefix_table: str) -> list[sa.Column]:
    return [
        sa.Column("version_label", sa.String(length=255), nullable=True),
        sa.Column("commit_sha", sa.String(length=128), nullable=True),
        sa.Column("tag", sa.String(length=255), nullable=True),
        sa.Column("version", sa.String(length=255), nullable=True),
        sa.Column("checksum", sa.String(length=255), nullable=True),
        sa.Column(
            "first_containing_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f(
                    f"fk_{prefix_table}_first_containing_version_id_source_versions"
                ),
            ),
            nullable=True,
        ),
        sa.Column(
            "last_containing_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f(
                    f"fk_{prefix_table}_last_containing_version_id_source_versions"
                ),
            ),
            nullable=True,
        ),
        sa.Column(
            "is_current",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    """Create the canonical source-backed relational model."""

    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("config_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("repository_url", sa.String(length=2048), nullable=True),
        sa.Column("artifact_url", sa.String(length=2048), nullable=True),
        sa.Column("default_branch", sa.String(length=255), nullable=True),
        sa.Column(
            "authority_rank",
            sa.Integer(),
            server_default=sa.text("100"),
            nullable=False,
        ),
        sa.Column(
            "visibility_label",
            sa.String(length=100),
            server_default="public",
            nullable=False,
        ),
        sa.Column(
            "sensitivity_class",
            sa.String(length=100),
            server_default="unknown",
            nullable=False,
        ),
        *timestamp_columns(),
        pk("sources"),
        sa.UniqueConstraint("config_key", name=op.f("uq_sources_config_key")),
    )

    op.create_table(
        "source_versions",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "source_id",
            sa.String(length=255),
            sa.ForeignKey(
                "sources.id", name=op.f("fk_source_versions_source_id_sources")
            ),
            nullable=False,
        ),
        sa.Column("version_label", sa.String(length=255), nullable=False),
        sa.Column("resolved_ref", sa.String(length=255), nullable=True),
        sa.Column("repository_url", sa.String(length=2048), nullable=True),
        sa.Column("artifact_url", sa.String(length=2048), nullable=True),
        sa.Column("commit_sha", sa.String(length=128), nullable=True),
        sa.Column("tag", sa.String(length=255), nullable=True),
        sa.Column("version", sa.String(length=255), nullable=True),
        sa.Column("checksum", sa.String(length=255), nullable=True),
        sa.Column("branch", sa.String(length=255), nullable=True),
        sa.Column(
            "is_current", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        *timestamp_columns(),
        pk("source_versions"),
        sa.UniqueConstraint(
            "source_id",
            "version_label",
            name=op.f("uq_source_versions_source_id_version_label"),
        ),
    )

    op.create_table(
        "source_changes",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "source_id",
            sa.String(length=255),
            sa.ForeignKey(
                "sources.id", name=op.f("fk_source_changes_source_id_sources")
            ),
            nullable=False,
        ),
        sa.Column("change_key", sa.String(length=255), nullable=False),
        sa.Column("change_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("commit_sha", sa.String(length=128), nullable=True),
        sa.Column("tag", sa.String(length=255), nullable=True),
        sa.Column("version", sa.String(length=255), nullable=True),
        sa.Column("checksum", sa.String(length=255), nullable=True),
        sa.Column("authored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        pk("source_changes"),
        sa.UniqueConstraint(
            "source_id",
            "change_key",
            name=op.f("uq_source_changes_source_id_change_key"),
        ),
    )

    op.create_table(
        "change_versions",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "change_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_changes.id",
                name=op.f("fk_change_versions_change_id_source_changes"),
            ),
            nullable=False,
        ),
        sa.Column(
            "source_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f("fk_change_versions_source_version_id_source_versions"),
            ),
            nullable=False,
        ),
        sa.Column("version_label", sa.String(length=255), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        pk("change_versions"),
        sa.UniqueConstraint(
            "change_id",
            "source_version_id",
            name=op.f("uq_change_versions_change_id_source_version_id"),
        ),
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "source_id",
            sa.String(length=255),
            sa.ForeignKey(
                "sources.id", name=op.f("fk_ingestion_runs_source_id_sources")
            ),
            nullable=True,
        ),
        sa.Column(
            "source_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f("fk_ingestion_runs_source_version_id_source_versions"),
            ),
            nullable=True,
        ),
        sa.Column("requested_ref", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        pk("ingestion_runs"),
    )

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=255), nullable=False),
        *provenance_columns("artifacts"),
        sa.Column("artifact_key", sa.String(length=1024), nullable=False),
        sa.Column("artifact_type", sa.String(length=100), nullable=False),
        sa.Column("artifact_role", sa.String(length=100), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("language", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column(
            "is_generated",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_vendored", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("sanitized_content_hash", sa.String(length=255), nullable=True),
        *timestamp_columns(),
        pk("artifacts"),
        sa.UniqueConstraint(
            "source_id",
            "artifact_key",
            name=op.f("uq_artifacts_source_id_artifact_key"),
        ),
    )

    op.create_table(
        "artifact_versions",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "artifact_id",
            sa.String(length=255),
            sa.ForeignKey(
                "artifacts.id", name=op.f("fk_artifact_versions_artifact_id_artifacts")
            ),
            nullable=False,
        ),
        sa.Column(
            "source_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f("fk_artifact_versions_source_version_id_source_versions"),
            ),
            nullable=False,
        ),
        *version_lineage_columns("artifact_versions"),
        pk("artifact_versions"),
        sa.UniqueConstraint(
            "artifact_id",
            "source_version_id",
            name=op.f("uq_artifact_versions_artifact_id_source_version_id"),
        ),
    )

    op.create_table(
        "artifact_extractions",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "artifact_id",
            sa.String(length=255),
            sa.ForeignKey(
                "artifacts.id",
                name=op.f("fk_artifact_extractions_artifact_id_artifacts"),
            ),
            nullable=False,
        ),
        sa.Column(
            "ingestion_run_id",
            sa.String(length=255),
            sa.ForeignKey(
                "ingestion_runs.id",
                name=op.f("fk_artifact_extractions_ingestion_run_id_ingestion_runs"),
            ),
            nullable=True,
        ),
        sa.Column(
            "source_id",
            sa.String(length=255),
            sa.ForeignKey(
                "sources.id", name=op.f("fk_artifact_extractions_source_id_sources")
            ),
            nullable=False,
        ),
        sa.Column(
            "source_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f("fk_artifact_extractions_source_version_id_source_versions"),
            ),
            nullable=True,
        ),
        sa.Column("extractor_name", sa.String(length=255), nullable=False),
        sa.Column("extractor_version", sa.String(length=255), nullable=True),
        sa.Column("extractor_profile", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("diagnostics", sa.JSON(), nullable=False),
        sa.Column("sanitized_content_hash", sa.String(length=255), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        pk("artifact_extractions"),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.String(length=255), nullable=False),
        *provenance_columns("chunks"),
        sa.Column("chunk_key", sa.String(length=1024), nullable=False),
        sa.Column(
            "artifact_id",
            sa.String(length=255),
            sa.ForeignKey("artifacts.id", name=op.f("fk_chunks_artifact_id_artifacts")),
            nullable=False,
        ),
        sa.Column(
            "extraction_id",
            sa.String(length=255),
            sa.ForeignKey(
                "artifact_extractions.id",
                name=op.f("fk_chunks_extraction_id_artifact_extractions"),
            ),
            nullable=True,
        ),
        sa.Column("sanitized_text", sa.Text(), nullable=False),
        sa.Column("sanitized_content_hash", sa.String(length=255), nullable=False),
        sa.Column("heading_path", sa.Text(), nullable=True),
        sa.Column("symbol_path", sa.String(length=2048), nullable=True),
        sa.Column("signature_text", sa.Text(), nullable=True),
        sa.Column("artifact_path", sa.String(length=2048), nullable=False),
        sa.Column("language", sa.String(length=100), nullable=True),
        sa.Column("artifact_role", sa.String(length=100), nullable=True),
        sa.Column("chunk_kind", sa.String(length=100), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        pk("chunks"),
        sa.UniqueConstraint(
            "source_id",
            "chunk_key",
            name=op.f("uq_chunks_source_id_chunk_key"),
        ),
    )

    op.create_table(
        "chunk_versions",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "chunk_id",
            sa.String(length=255),
            sa.ForeignKey("chunks.id", name=op.f("fk_chunk_versions_chunk_id_chunks")),
            nullable=False,
        ),
        sa.Column(
            "source_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f("fk_chunk_versions_source_version_id_source_versions"),
            ),
            nullable=False,
        ),
        *version_lineage_columns("chunk_versions"),
        pk("chunk_versions"),
        sa.UniqueConstraint(
            "chunk_id",
            "source_version_id",
            name=op.f("uq_chunk_versions_chunk_id_source_version_id"),
        ),
    )

    op.create_table(
        "citations",
        sa.Column("id", sa.String(length=255), nullable=False),
        *provenance_columns("citations"),
        sa.Column("citation_key", sa.String(length=1024), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column(
            "artifact_id",
            sa.String(length=255),
            sa.ForeignKey(
                "artifacts.id", name=op.f("fk_citations_artifact_id_artifacts")
            ),
            nullable=True,
        ),
        sa.Column(
            "chunk_id",
            sa.String(length=255),
            sa.ForeignKey("chunks.id", name=op.f("fk_citations_chunk_id_chunks")),
            nullable=True,
        ),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("sanitized_content_hash", sa.String(length=255), nullable=False),
        pk("citations"),
        sa.UniqueConstraint("citation_key", name=op.f("uq_citations_citation_key")),
        sa.CheckConstraint(
            "(line_start IS NULL AND line_end IS NULL) OR "
            "(line_start IS NOT NULL AND line_end IS NOT NULL "
            "AND line_start <= line_end)",
            name=op.f("ck_citations_line_range_order"),
        ),
    )

    op.create_table(
        "facts",
        sa.Column("id", sa.String(length=255), nullable=False),
        *provenance_columns("facts"),
        sa.Column("fact_key", sa.String(length=1024), nullable=False),
        sa.Column(
            "artifact_id",
            sa.String(length=255),
            sa.ForeignKey("artifacts.id", name=op.f("fk_facts_artifact_id_artifacts")),
            nullable=True,
        ),
        sa.Column(
            "extraction_id",
            sa.String(length=255),
            sa.ForeignKey(
                "artifact_extractions.id",
                name=op.f("fk_facts_extraction_id_artifact_extractions"),
            ),
            nullable=True,
        ),
        sa.Column("fact_type", sa.String(length=100), nullable=False),
        sa.Column("subject", sa.String(length=1024), nullable=True),
        sa.Column("predicate", sa.String(length=255), nullable=True),
        sa.Column("normalized_value", sa.JSON(), nullable=True),
        sa.Column("value_type", sa.String(length=100), nullable=True),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("authority_rank", sa.Integer(), nullable=True),
        sa.Column(
            "primary_citation_id",
            sa.String(length=255),
            sa.ForeignKey(
                "citations.id", name=op.f("fk_facts_primary_citation_id_citations")
            ),
            nullable=True,
        ),
        sa.Column("citation_ids", sa.JSON(), nullable=False),
        sa.Column("sanitized_content_hash", sa.String(length=255), nullable=True),
        pk("facts"),
        sa.UniqueConstraint(
            "source_id",
            "fact_key",
            name=op.f("uq_facts_source_id_fact_key"),
        ),
    )

    op.create_table(
        "fact_versions",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "fact_id",
            sa.String(length=255),
            sa.ForeignKey("facts.id", name=op.f("fk_fact_versions_fact_id_facts")),
            nullable=False,
        ),
        sa.Column(
            "source_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f("fk_fact_versions_source_version_id_source_versions"),
            ),
            nullable=False,
        ),
        *version_lineage_columns("fact_versions"),
        pk("fact_versions"),
        sa.UniqueConstraint(
            "fact_id",
            "source_version_id",
            name=op.f("uq_fact_versions_fact_id_source_version_id"),
        ),
    )

    op.create_table(
        "claims",
        sa.Column("id", sa.String(length=255), nullable=False),
        *provenance_columns("claims"),
        sa.Column("claim_key", sa.String(length=1024), nullable=False),
        sa.Column(
            "fact_id",
            sa.String(length=255),
            sa.ForeignKey("facts.id", name=op.f("fk_claims_fact_id_facts")),
            nullable=True,
        ),
        sa.Column("subject", sa.String(length=1024), nullable=False),
        sa.Column("predicate", sa.String(length=255), nullable=False),
        sa.Column("normalized_value", sa.JSON(), nullable=False),
        sa.Column("value_type", sa.String(length=100), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("authority_rank", sa.Integer(), nullable=False),
        sa.Column(
            "primary_citation_id",
            sa.String(length=255),
            sa.ForeignKey(
                "citations.id", name=op.f("fk_claims_primary_citation_id_citations")
            ),
            nullable=False,
        ),
        sa.Column("citation_ids", sa.JSON(), nullable=False),
        sa.Column("sanitized_content_hash", sa.String(length=255), nullable=True),
        pk("claims"),
        sa.UniqueConstraint(
            "source_id",
            "claim_key",
            name=op.f("uq_claims_source_id_claim_key"),
        ),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name=op.f("ck_claims_confidence_range"),
        ),
    )

    op.create_table(
        "claim_versions",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "claim_id",
            sa.String(length=255),
            sa.ForeignKey("claims.id", name=op.f("fk_claim_versions_claim_id_claims")),
            nullable=False,
        ),
        sa.Column(
            "source_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f("fk_claim_versions_source_version_id_source_versions"),
            ),
            nullable=False,
        ),
        *version_lineage_columns("claim_versions"),
        pk("claim_versions"),
        sa.UniqueConstraint(
            "claim_id",
            "source_version_id",
            name=op.f("uq_claim_versions_claim_id_source_version_id"),
        ),
    )

    op.create_table(
        "claim_conflicts",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("conflict_key", sa.String(length=1024), nullable=False),
        sa.Column(
            "left_claim_id",
            sa.String(length=255),
            sa.ForeignKey(
                "claims.id", name=op.f("fk_claim_conflicts_left_claim_id_claims")
            ),
            nullable=False,
        ),
        sa.Column(
            "right_claim_id",
            sa.String(length=255),
            sa.ForeignKey(
                "claims.id", name=op.f("fk_claim_conflicts_right_claim_id_claims")
            ),
            nullable=False,
        ),
        sa.Column(
            "primary_citation_id",
            sa.String(length=255),
            sa.ForeignKey(
                "citations.id",
                name=op.f("fk_claim_conflicts_primary_citation_id_citations"),
            ),
            nullable=False,
        ),
        sa.Column("overlap_scope", sa.JSON(), nullable=False),
        sa.Column("evidence_citation_ids", sa.JSON(), nullable=False),
        sa.Column(
            "status", sa.String(length=100), server_default="unresolved", nullable=False
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        pk("claim_conflicts"),
        sa.UniqueConstraint(
            "conflict_key", name=op.f("uq_claim_conflicts_conflict_key")
        ),
        sa.CheckConstraint(
            "left_claim_id <> right_claim_id",
            name=op.f("ck_claim_conflicts_different_claims"),
        ),
    )

    op.create_table(
        "relationships",
        sa.Column("id", sa.String(length=255), nullable=False),
        *provenance_columns("relationships"),
        sa.Column("relationship_key", sa.String(length=1024), nullable=False),
        sa.Column("relationship_type", sa.String(length=100), nullable=False),
        sa.Column("from_entity_type", sa.String(length=100), nullable=False),
        sa.Column("from_entity_id", sa.String(length=255), nullable=False),
        sa.Column("to_entity_type", sa.String(length=100), nullable=False),
        sa.Column("to_entity_id", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("authority_rank", sa.Integer(), nullable=True),
        sa.Column(
            "primary_citation_id",
            sa.String(length=255),
            sa.ForeignKey(
                "citations.id",
                name=op.f("fk_relationships_primary_citation_id_citations"),
            ),
            nullable=False,
        ),
        sa.Column("citation_ids", sa.JSON(), nullable=False),
        sa.Column("sanitized_content_hash", sa.String(length=255), nullable=True),
        pk("relationships"),
        sa.UniqueConstraint(
            "source_id",
            "relationship_key",
            name=op.f("uq_relationships_source_id_relationship_key"),
        ),
        sa.CheckConstraint(
            "relationship_type IN ('contains', 'defines', 'references', "
            "'derived_from', 'cites', 'introduced_in', 'removed_in', "
            "'changed_by', 'conflicts_with')",
            name=op.f("ck_relationships_relationship_type_valid"),
        ),
    )

    op.create_table(
        "relationship_versions",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "relationship_id",
            sa.String(length=255),
            sa.ForeignKey(
                "relationships.id",
                name=op.f("fk_relationship_versions_relationship_id_relationships"),
            ),
            nullable=False,
        ),
        sa.Column(
            "source_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "source_versions.id",
                name=op.f("fk_relationship_versions_source_version_id_source_versions"),
            ),
            nullable=False,
        ),
        *version_lineage_columns("relationship_versions"),
        pk("relationship_versions"),
        sa.UniqueConstraint(
            "relationship_id",
            "source_version_id",
            name=op.f("uq_relationship_versions_relationship_id_source_version_id"),
        ),
    )


def downgrade() -> None:
    """Drop the canonical source-backed relational model."""

    op.drop_table("relationship_versions")
    op.drop_table("relationships")
    op.drop_table("claim_conflicts")
    op.drop_table("claim_versions")
    op.drop_table("claims")
    op.drop_table("fact_versions")
    op.drop_table("facts")
    op.drop_table("citations")
    op.drop_table("chunk_versions")
    op.drop_table("chunks")
    op.drop_table("artifact_extractions")
    op.drop_table("artifact_versions")
    op.drop_table("artifacts")
    op.drop_table("ingestion_runs")
    op.drop_table("change_versions")
    op.drop_table("source_changes")
    op.drop_table("source_versions")
    op.drop_table("sources")
