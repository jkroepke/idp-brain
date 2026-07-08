"""Index version records for retrievable sanitized corpus state."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from idp_brain.models.base import Base, TimestampMixin, new_id

INDEX_KINDS: Final[tuple[str, ...]] = ("exact", "bm25", "vector", "hybrid")
INDEX_STATUSES: Final[tuple[str, ...]] = (
    "building",
    "inactive",
    "active",
    "retired",
    "failed",
)

INDEX_KIND_CHECK: Final[str] = "index_kind IN ({})".format(
    ", ".join(f"'{kind}'" for kind in INDEX_KINDS)
)
INDEX_STATUS_CHECK: Final[str] = "status IN ({})".format(
    ", ".join(f"'{status}'" for status in INDEX_STATUSES)
)


class IndexVersion(TimestampMixin, Base):
    """Blue/green index generation that can be activated or rolled back."""

    __tablename__ = "index_versions"
    __table_args__ = (
        Index("ix_index_versions_status", "status", "activated_at", "retired_at"),
        Index("ix_index_versions_embedding_model_id", "embedding_model_id"),
        Index(
            "ix_index_versions_built_from_ingestion_run_id",
            "built_from_ingestion_run_id",
        ),
        CheckConstraint(INDEX_KIND_CHECK, name="index_kind_valid"),
        CheckConstraint(INDEX_STATUS_CHECK, name="status_valid"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    index_kind: Mapped[str] = mapped_column(String(100), nullable=False)
    corpus_scope: Mapped[str] = mapped_column(String(255), nullable=False)
    source_scope: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    embedding_model_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("embedding_models.id"),
    )
    bm25_profile: Mapped[str | None] = mapped_column(String(255))
    vector_profile: Mapped[str | None] = mapped_column(String(255))
    exact_index_profile: Mapped[str | None] = mapped_column(String(255))
    relationship_profile: Mapped[str | None] = mapped_column(String(255))
    chunking_profile: Mapped[str | None] = mapped_column(String(255))
    reranker_profile: Mapped[str | None] = mapped_column(String(255))
    config_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(100), default="inactive", nullable=False)
    built_from_ingestion_run_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("ingestion_runs.id"),
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
