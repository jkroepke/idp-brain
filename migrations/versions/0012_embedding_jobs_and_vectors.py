"""Complete embedding job and active vector storage fields."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_embedding_jobs_vectors"
down_revision: str | None = "0011_incremental_membership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add content-hash and active-vector bookkeeping for 4.2."""

    op.add_column(
        "embeddings",
        sa.Column("sanitized_content_hash", sa.String(length=255), nullable=True),
    )
    op.execute(
        "UPDATE embeddings SET sanitized_content_hash = sanitized_input_hash "
        "WHERE sanitized_content_hash IS NULL"
    )
    op.alter_column("embeddings", "sanitized_content_hash", nullable=False)
    op.add_column(
        "embeddings",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "embeddings",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_embeddings_active_scope"),
        "embeddings",
        ["index_version_id", "is_active"],
    )

    op.add_column(
        "embedding_jobs",
        sa.Column("sanitized_content_hash", sa.String(length=255), nullable=True),
    )
    op.execute(
        "UPDATE embedding_jobs SET sanitized_content_hash = sanitized_input_hash "
        "WHERE sanitized_content_hash IS NULL"
    )
    op.alter_column("embedding_jobs", "sanitized_content_hash", nullable=False)
    op.create_unique_constraint(
        op.f(
            "uq_embedding_jobs_chunk_id_embedding_model_id_index_version_id_"
            "sanitized_content_hash"
        ),
        "embedding_jobs",
        [
            "chunk_id",
            "embedding_model_id",
            "index_version_id",
            "sanitized_content_hash",
        ],
    )


def downgrade() -> None:
    """Remove 4.2 active-vector bookkeeping fields."""

    op.drop_constraint(
        op.f(
            "uq_embedding_jobs_chunk_id_embedding_model_id_index_version_id_"
            "sanitized_content_hash"
        ),
        "embedding_jobs",
        type_="unique",
    )
    op.drop_column("embedding_jobs", "sanitized_content_hash")

    op.drop_index(op.f("ix_embeddings_active_scope"), table_name="embeddings")
    op.drop_column("embeddings", "updated_at")
    op.drop_column("embeddings", "is_active")
    op.drop_column("embeddings", "sanitized_content_hash")
