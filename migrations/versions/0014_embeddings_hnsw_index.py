"""Add pgvector HNSW indexes for active embedding vectors."""

from collections.abc import Sequence

from alembic import op

revision: str = "0014_embeddings_hnsw_index"
down_revision: str | None = "0013_chunks_bm25_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDINGS_HNSW_INDEXES = {
    32: "embeddings_hnsw_cosine_32_idx",
    64: "embeddings_hnsw_cosine_64_idx",
}
EMBEDDINGS_IS_ACTIVE_INDEX = "ix_embeddings_is_active"


def upgrade() -> None:
    """Create ANN indexes while keeping exact vector ordering available."""

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_index(
        EMBEDDINGS_IS_ACTIVE_INDEX,
        "embeddings",
        ["is_active"],
        if_not_exists=True,
    )

    # The embeddings.vector column intentionally allows mixed dimensions.
    # pgvector indexes require an explicit dimension, so these partial
    # expression indexes map to the enabled MVP mock profiles in config:
    # docs_default/code_default/memory_default -> 32, docs_quality -> 64.
    for dimensions, index_name in EMBEDDINGS_HNSW_INDEXES.items():
        op.execute(
            f"""
            CREATE INDEX {index_name}
            ON embeddings
            USING hnsw ((vector::vector({dimensions})) vector_cosine_ops)
            WHERE dimensions = {dimensions} AND is_active
            """
        )


def downgrade() -> None:
    """Remove the migration-managed vector indexes."""

    for index_name in EMBEDDINGS_HNSW_INDEXES.values():
        op.drop_index(index_name, table_name="embeddings", if_exists=True)
    op.drop_index(EMBEDDINGS_IS_ACTIVE_INDEX, table_name="embeddings", if_exists=True)
