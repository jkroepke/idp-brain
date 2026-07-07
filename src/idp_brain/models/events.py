"""Sanitized operational event records."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from idp_brain.models.base import Base, TimestampMixin, new_id, utc_now
from idp_brain.models.policy import REDACTION_STATUS_CHECK

CORPUS_ELIGIBILITY_RESULTS: Final[tuple[str, ...]] = (
    "allowed",
    "blocked",
    "partial",
    "diagnostic_only",
)

CORPUS_ELIGIBILITY_RESULT_CHECK: Final[str] = (
    "corpus_eligibility_filter_result IN ({})".format(
        ", ".join(f"'{result}'" for result in CORPUS_ELIGIBILITY_RESULTS)
    )
)


class RetrievalEvent(TimestampMixin, Base):
    """Sanitized retrieval diagnostics without raw chunks or sensitive query text."""

    __tablename__ = "retrieval_events"
    __table_args__ = (
        Index("ix_retrieval_events_query_hash", "query_hash"),
        Index("ix_retrieval_events_ingestion_run_id", "ingestion_run_id"),
        Index("ix_retrieval_events_source_id", "source_id"),
        Index(
            "ix_retrieval_events_primary_selected_chunk_id",
            "primary_selected_chunk_id",
        ),
        Index(
            "ix_retrieval_events_primary_selected_citation_id",
            "primary_selected_citation_id",
        ),
        Index(
            "ix_retrieval_events_primary_selected_artifact_id",
            "primary_selected_artifact_id",
        ),
        Index("ix_retrieval_events_active_index_version_id", "active_index_version_id"),
        Index(
            "ix_retrieval_events_filter_result",
            "corpus_eligibility_filter_result",
            "redaction_status",
        ),
        CheckConstraint(
            "query_token_count >= 0", name="query_token_count_non_negative"
        ),
        CheckConstraint(REDACTION_STATUS_CHECK, name="redaction_status_valid"),
        CheckConstraint(
            CORPUS_ELIGIBILITY_RESULT_CHECK,
            name="corpus_eligibility_filter_result_valid",
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    ingestion_run_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("ingestion_runs.id"),
    )
    source_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("sources.id"))
    source_version_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("source_versions.id"),
    )
    query_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    sanitized_query_preview: Mapped[str | None] = mapped_column(String(512))
    query_token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trusted_filters: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    selected_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    primary_selected_chunk_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("chunks.id"),
    )
    primary_selected_citation_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("citations.id"),
    )
    primary_selected_artifact_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("artifacts.id"),
    )
    selected_chunk_ids: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    selected_citation_ids: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    selected_artifact_ids: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    ranking_diagnostics: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    redaction_status: Mapped[str] = mapped_column(
        String(100),
        default="unknown",
        nullable=False,
    )
    corpus_eligibility_filter_result: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    active_index_version_id: Mapped[str | None] = mapped_column(String(255))
    searched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
