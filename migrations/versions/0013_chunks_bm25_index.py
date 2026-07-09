"""Add ParadeDB BM25 index over sanitized chunks."""

from collections.abc import Sequence

from alembic import op

revision: str = "0013_chunks_bm25_index"
down_revision: str | None = "0012_embedding_jobs_vectors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHUNKS_BM25_INDEX_NAME = "chunks_bm25_idx"
CHUNKS_BM25_FIELDS = (
    "id",
    "sanitized_text",
    "heading_path",
    "symbol_path",
    "signature_text",
    "artifact_path",
    "source_type",
    "language",
    "version_label",
    "visibility_label",
    "sensitivity_class",
    "license_policy_status",
    "source_id",
    "artifact_role",
)


def upgrade() -> None:
    """Create the BM25 index used by later retrieval services."""

    fields = ",\n        ".join(CHUNKS_BM25_FIELDS)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_search")
    op.execute(
        f"""
        CREATE INDEX {CHUNKS_BM25_INDEX_NAME}
        ON chunks
        USING bm25 (
            {fields}
        )
        WITH (key_field = 'id')
        """
    )


def downgrade() -> None:
    """Remove the migration-managed BM25 index."""

    op.execute(f"DROP INDEX IF EXISTS {CHUNKS_BM25_INDEX_NAME}")
