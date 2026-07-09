"""Add exact lookup indexes over sanitized chunks."""

from collections.abc import Sequence

from alembic import op

revision: str = "0015_chunks_exact_lookup_indexes"
down_revision: str | None = "0014_embeddings_hnsw_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXACT_INDEXES = (
    "chunks_exact_symbol_idx",
    "chunks_exact_artifact_path_idx",
    "chunks_exact_heading_idx",
    "chunks_exact_signature_idx",
    "chunks_exact_source_type_idx",
    "chunks_exact_version_idx",
)


def upgrade() -> None:
    """Create B-tree indexes for sanitized exact lookup metadata."""

    op.create_index(
        "chunks_exact_symbol_idx",
        "chunks",
        ["source_id", "version_label", "language", "symbol_path"],
        postgresql_where="symbol_path IS NOT NULL",
        if_not_exists=True,
    )
    op.create_index(
        "chunks_exact_artifact_path_idx",
        "chunks",
        ["source_id", "version_label", "artifact_path"],
        if_not_exists=True,
    )
    op.create_index(
        "chunks_exact_heading_idx",
        "chunks",
        ["source_id", "version_label", "heading_path"],
        postgresql_where="heading_path IS NOT NULL",
        if_not_exists=True,
    )
    op.create_index(
        "chunks_exact_signature_idx",
        "chunks",
        ["source_id", "version_label", "signature_text"],
        postgresql_where="signature_text IS NOT NULL",
        if_not_exists=True,
    )
    op.create_index(
        "chunks_exact_source_type_idx",
        "chunks",
        ["source_type", "source_id", "version_label"],
        if_not_exists=True,
    )
    op.create_index(
        "chunks_exact_version_idx",
        "chunks",
        ["version_label", "source_id", "artifact_path"],
        postgresql_where="version_label IS NOT NULL",
        if_not_exists=True,
    )


def downgrade() -> None:
    """Remove exact lookup indexes."""

    for index_name in reversed(EXACT_INDEXES):
        op.drop_index(index_name, table_name="chunks", if_exists=True)
