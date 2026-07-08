"""Add index versions, embedding models, vectors, and jobs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR

revision: str = "0005_index_embeddings"
down_revision: str | None = "0004_redaction_license_events"
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
    """Create deterministic index and embedding state tables."""

    op.create_table(
        "embedding_models",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("provider_name", sa.String(length=255), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("provider_model_id", sa.String(length=255), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("modality", sa.String(length=100), nullable=False),
        sa.Column("corpus_scope", sa.String(length=255), nullable=False),
        sa.Column("distance_metric", sa.String(length=100), nullable=False),
        sa.Column("tokenizer_profile", sa.String(length=255), nullable=True),
        sa.Column("config_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "deterministic",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "external_calls_allowed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "promotion_status",
            sa.String(length=100),
            server_default="inactive",
            nullable=False,
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        pk("embedding_models"),
        sa.UniqueConstraint(
            "provider_name",
            "provider_model_id",
            "config_hash",
            name=op.f(
                "uq_embedding_models_provider_name_provider_model_id_config_hash"
            ),
        ),
        sa.CheckConstraint(
            "dimensions > 0",
            name=op.f("ck_embedding_models_dimensions_positive"),
        ),
        sa.CheckConstraint(
            "distance_metric IN ('cosine', 'l2', 'inner_product', 'l1')",
            name=op.f("ck_embedding_models_distance_metric_valid"),
        ),
        sa.CheckConstraint(
            "promotion_status IN "
            "('mock', 'inactive', 'candidate', 'promoted', 'retired')",
            name=op.f("ck_embedding_models_promotion_status_valid"),
        ),
    )
    op.create_index(
        op.f("ix_embedding_models_promotion_status"),
        "embedding_models",
        ["promotion_status"],
    )

    op.create_table(
        "index_versions",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("index_kind", sa.String(length=100), nullable=False),
        sa.Column("corpus_scope", sa.String(length=255), nullable=False),
        sa.Column("source_scope", sa.JSON(), nullable=False),
        sa.Column(
            "embedding_model_id",
            sa.String(length=255),
            sa.ForeignKey(
                "embedding_models.id",
                name=op.f("fk_index_versions_embedding_model_id_embedding_models"),
            ),
            nullable=True,
        ),
        sa.Column("bm25_profile", sa.String(length=255), nullable=True),
        sa.Column("vector_profile", sa.String(length=255), nullable=True),
        sa.Column("exact_index_profile", sa.String(length=255), nullable=True),
        sa.Column("relationship_profile", sa.String(length=255), nullable=True),
        sa.Column("chunking_profile", sa.String(length=255), nullable=True),
        sa.Column("reranker_profile", sa.String(length=255), nullable=True),
        sa.Column("config_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=100),
            server_default="inactive",
            nullable=False,
        ),
        sa.Column(
            "built_from_ingestion_run_id",
            sa.String(length=255),
            sa.ForeignKey(
                "ingestion_runs.id",
                name=op.f(
                    "fk_index_versions_built_from_ingestion_run_id_ingestion_runs"
                ),
            ),
            nullable=True,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_metadata", sa.JSON(), nullable=False),
        *timestamp_columns(),
        pk("index_versions"),
        sa.UniqueConstraint("name", name=op.f("uq_index_versions_name")),
        sa.CheckConstraint(
            "index_kind IN ('exact', 'bm25', 'vector', 'hybrid')",
            name=op.f("ck_index_versions_index_kind_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('building', 'inactive', 'active', 'retired', 'failed')",
            name=op.f("ck_index_versions_status_valid"),
        ),
    )
    op.create_index(
        op.f("ix_index_versions_status"),
        "index_versions",
        ["status", "activated_at", "retired_at"],
    )
    op.create_index(
        op.f("ix_index_versions_embedding_model_id"),
        "index_versions",
        ["embedding_model_id"],
    )
    op.create_index(
        op.f("ix_index_versions_built_from_ingestion_run_id"),
        "index_versions",
        ["built_from_ingestion_run_id"],
    )

    op.create_foreign_key(
        op.f("fk_retrieval_events_active_index_version_id_index_versions"),
        "retrieval_events",
        "index_versions",
        ["active_index_version_id"],
        ["id"],
    )

    op.create_table(
        "embeddings",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "chunk_id",
            sa.String(length=255),
            sa.ForeignKey("chunks.id", name=op.f("fk_embeddings_chunk_id_chunks")),
            nullable=False,
        ),
        sa.Column(
            "embedding_model_id",
            sa.String(length=255),
            sa.ForeignKey(
                "embedding_models.id",
                name=op.f("fk_embeddings_embedding_model_id_embedding_models"),
            ),
            nullable=False,
        ),
        sa.Column(
            "index_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "index_versions.id",
                name=op.f("fk_embeddings_index_version_id_index_versions"),
            ),
            nullable=False,
        ),
        sa.Column("sanitized_input_hash", sa.String(length=255), nullable=False),
        sa.Column("vector", VECTOR(), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("distance_metric", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        pk("embeddings"),
        sa.UniqueConstraint(
            "chunk_id",
            "embedding_model_id",
            "index_version_id",
            "sanitized_input_hash",
            name=op.f(
                "uq_embeddings_chunk_id_embedding_model_id_index_version_id_"
                "sanitized_input_hash"
            ),
        ),
        sa.CheckConstraint(
            "dimensions > 0",
            name=op.f("ck_embeddings_dimensions_positive"),
        ),
        sa.CheckConstraint(
            "distance_metric IN ('cosine', 'l2', 'inner_product', 'l1')",
            name=op.f("ck_embeddings_distance_metric_valid"),
        ),
    )
    op.create_index(op.f("ix_embeddings_chunk_id"), "embeddings", ["chunk_id"])
    op.create_index(
        op.f("ix_embeddings_embedding_model_id"),
        "embeddings",
        ["embedding_model_id"],
    )
    op.create_index(
        op.f("ix_embeddings_index_version_id"),
        "embeddings",
        ["index_version_id"],
    )

    op.create_table(
        "embedding_jobs",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column(
            "chunk_id",
            sa.String(length=255),
            sa.ForeignKey("chunks.id", name=op.f("fk_embedding_jobs_chunk_id_chunks")),
            nullable=False,
        ),
        sa.Column(
            "embedding_model_id",
            sa.String(length=255),
            sa.ForeignKey(
                "embedding_models.id",
                name=op.f("fk_embedding_jobs_embedding_model_id_embedding_models"),
            ),
            nullable=False,
        ),
        sa.Column(
            "index_version_id",
            sa.String(length=255),
            sa.ForeignKey(
                "index_versions.id",
                name=op.f("fk_embedding_jobs_index_version_id_index_versions"),
            ),
            nullable=False,
        ),
        sa.Column("sanitized_input_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=100),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_request_hash", sa.String(length=255), nullable=True),
        sa.Column("provider_response_metadata", sa.JSON(), nullable=False),
        sa.Column("sanitized_error_code", sa.String(length=255), nullable=True),
        sa.Column("sanitized_error_message", sa.Text(), nullable=True),
        *timestamp_columns(),
        pk("embedding_jobs"),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=op.f("ck_embedding_jobs_attempt_count_non_negative"),
        ),
        sa.CheckConstraint(
            "status IN "
            "('pending', 'running', 'succeeded', 'retrying', 'failed', 'cancelled')",
            name=op.f("ck_embedding_jobs_status_valid"),
        ),
    )
    op.create_index(
        op.f("ix_embedding_jobs_status_retry"),
        "embedding_jobs",
        ["status", "next_retry_at"],
    )
    op.create_index(
        op.f("ix_embedding_jobs_chunk_id"),
        "embedding_jobs",
        ["chunk_id"],
    )
    op.create_index(
        op.f("ix_embedding_jobs_embedding_model_id"),
        "embedding_jobs",
        ["embedding_model_id"],
    )
    op.create_index(
        op.f("ix_embedding_jobs_index_version_id"),
        "embedding_jobs",
        ["index_version_id"],
    )


def downgrade() -> None:
    """Drop deterministic index and embedding state tables."""

    for index_name in (
        "ix_embedding_jobs_index_version_id",
        "ix_embedding_jobs_embedding_model_id",
        "ix_embedding_jobs_chunk_id",
        "ix_embedding_jobs_status_retry",
    ):
        op.drop_index(op.f(index_name), "embedding_jobs")
    op.drop_table("embedding_jobs")

    for index_name in (
        "ix_embeddings_index_version_id",
        "ix_embeddings_embedding_model_id",
        "ix_embeddings_chunk_id",
    ):
        op.drop_index(op.f(index_name), "embeddings")
    op.drop_table("embeddings")

    op.drop_constraint(
        op.f("fk_retrieval_events_active_index_version_id_index_versions"),
        "retrieval_events",
        type_="foreignkey",
    )

    for index_name in (
        "ix_index_versions_built_from_ingestion_run_id",
        "ix_index_versions_embedding_model_id",
        "ix_index_versions_status",
    ):
        op.drop_index(op.f(index_name), "index_versions")
    op.drop_table("index_versions")

    op.drop_index(op.f("ix_embedding_models_promotion_status"), "embedding_models")
    op.drop_table("embedding_models")
