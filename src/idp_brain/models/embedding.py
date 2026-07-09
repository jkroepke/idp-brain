"""Embedding model registry, vectors, and safe local job records."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

from pgvector.sqlalchemy import VECTOR  # type: ignore[import-untyped]
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from idp_brain.models.base import Base, TimestampMixin, new_id, utc_now

DISTANCE_METRICS: Final[tuple[str, ...]] = ("cosine", "l2", "inner_product", "l1")
EMBEDDING_MODEL_STATUSES: Final[tuple[str, ...]] = (
    "mock",
    "inactive",
    "candidate",
    "promoted",
    "retired",
)
EMBEDDING_JOB_STATUSES: Final[tuple[str, ...]] = (
    "pending",
    "running",
    "succeeded",
    "retrying",
    "failed",
    "cancelled",
)

DISTANCE_METRIC_CHECK: Final[str] = "distance_metric IN ({})".format(
    ", ".join(f"'{metric}'" for metric in DISTANCE_METRICS)
)
EMBEDDING_MODEL_STATUS_CHECK: Final[str] = "promotion_status IN ({})".format(
    ", ".join(f"'{status}'" for status in EMBEDDING_MODEL_STATUSES)
)
EMBEDDING_JOB_STATUS_CHECK: Final[str] = "status IN ({})".format(
    ", ".join(f"'{status}'" for status in EMBEDDING_JOB_STATUSES)
)


class EmbeddingModel(TimestampMixin, Base):
    """Configured embedding model profile, including deterministic CI fixtures."""

    __tablename__ = "embedding_models"
    __table_args__ = (
        UniqueConstraint("provider_name", "provider_model_id", "config_hash"),
        Index("ix_embedding_models_promotion_status", "promotion_status"),
        CheckConstraint("dimensions > 0", name="dimensions_positive"),
        CheckConstraint(DISTANCE_METRIC_CHECK, name="distance_metric_valid"),
        CheckConstraint(EMBEDDING_MODEL_STATUS_CHECK, name="promotion_status_valid"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    provider_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    modality: Mapped[str] = mapped_column(String(100), nullable=False)
    corpus_scope: Mapped[str] = mapped_column(String(255), nullable=False)
    distance_metric: Mapped[str] = mapped_column(String(100), nullable=False)
    tokenizer_profile: Mapped[str | None] = mapped_column(String(255))
    config_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    deterministic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    external_calls_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    promotion_status: Mapped[str] = mapped_column(
        String(100),
        default="inactive",
        nullable=False,
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Embedding(Base):
    """Vector generated from a sanitized chunk hash for a specific index version."""

    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint(
            "chunk_id",
            "embedding_model_id",
            "index_version_id",
            "sanitized_input_hash",
        ),
        Index("ix_embeddings_chunk_id", "chunk_id"),
        Index("ix_embeddings_embedding_model_id", "embedding_model_id"),
        Index("ix_embeddings_index_version_id", "index_version_id"),
        Index("ix_embeddings_is_active", "is_active"),
        Index("ix_embeddings_active_scope", "index_version_id", "is_active"),
        CheckConstraint("dimensions > 0", name="dimensions_positive"),
        CheckConstraint(DISTANCE_METRIC_CHECK, name="distance_metric_valid"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    chunk_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("chunks.id"),
        nullable=False,
    )
    embedding_model_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("embedding_models.id"),
        nullable=False,
    )
    index_version_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("index_versions.id"),
        nullable=False,
    )
    sanitized_input_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    sanitized_content_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    vector: Mapped[list[float]] = mapped_column(VECTOR(), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_metric: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmbeddingJob(TimestampMixin, Base):
    """Safe embedding work item; stores hashes and sanitized metadata only."""

    __tablename__ = "embedding_jobs"
    __table_args__ = (
        Index("ix_embedding_jobs_status_retry", "status", "next_retry_at"),
        Index("ix_embedding_jobs_chunk_id", "chunk_id"),
        Index("ix_embedding_jobs_embedding_model_id", "embedding_model_id"),
        Index("ix_embedding_jobs_index_version_id", "index_version_id"),
        UniqueConstraint(
            "chunk_id",
            "embedding_model_id",
            "index_version_id",
            "sanitized_content_hash",
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_count_non_negative"),
        CheckConstraint(EMBEDDING_JOB_STATUS_CHECK, name="status_valid"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    chunk_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("chunks.id"),
        nullable=False,
    )
    embedding_model_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("embedding_models.id"),
        nullable=False,
    )
    index_version_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("index_versions.id"),
        nullable=False,
    )
    sanitized_input_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    sanitized_content_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(100), default="pending", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_request_hash: Mapped[str | None] = mapped_column(String(255))
    provider_response_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    sanitized_error_code: Mapped[str | None] = mapped_column(String(255))
    sanitized_error_message: Mapped[str | None] = mapped_column(Text)
