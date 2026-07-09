"""Sanitized redaction policy decision records."""

from __future__ import annotations

from datetime import datetime
from typing import Final

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from idp_brain.models.base import Base, TimestampMixin, new_id, utc_now
from idp_brain.models.policy import REDACTION_STATUS_CHECK

REDACTION_SEVERITIES: Final[tuple[str, ...]] = (
    "unknown",
    "low",
    "medium",
    "high",
    "critical",
)

REDACTION_SEVERITY_CHECK: Final[str] = "severity IN ({})".format(
    ", ".join(f"'{severity}'" for severity in REDACTION_SEVERITIES)
)


class RedactionEvent(TimestampMixin, Base):
    """Detector finding metadata without matched secret, PII, or raw text."""

    __tablename__ = "redaction_events"
    __table_args__ = (
        Index("ix_redaction_events_ingestion_run_id", "ingestion_run_id"),
        Index(
            "ix_redaction_events_source_version_artifact",
            "source_id",
            "source_version_id",
            "artifact_id",
        ),
        Index("ix_redaction_events_chunk_id", "chunk_id"),
        Index("ix_redaction_events_citation_id", "citation_id"),
        Index("ix_redaction_events_sanitized_content_hash", "sanitized_content_hash"),
        CheckConstraint("match_count >= 0", name="match_count_non_negative"),
        CheckConstraint(REDACTION_SEVERITY_CHECK, name="severity_valid"),
        CheckConstraint(REDACTION_STATUS_CHECK, name="redaction_status_valid"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    ingestion_run_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("ingestion_runs.id"),
        nullable=False,
    )
    source_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("sources.id"),
        nullable=False,
    )
    source_version_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("source_versions.id"),
    )
    artifact_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("artifacts.id"),
        nullable=False,
    )
    chunk_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("chunks.id"))
    citation_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("citations.id"),
    )
    detector_name: Mapped[str] = mapped_column(String(255), nullable=False)
    detector_version: Mapped[str | None] = mapped_column(String(255))
    rule_id: Mapped[str | None] = mapped_column(String(255))
    redaction_type: Mapped[str] = mapped_column(
        String(100),
        default="secret",
        nullable=False,
    )
    marker: Mapped[str] = mapped_column(String(255), nullable=False)
    match_count: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    location_locator: Mapped[str | None] = mapped_column(String(2048))
    sanitized_content_hash: Mapped[str | None] = mapped_column(String(255))
    redaction_profile: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(100),
        default="unknown",
        nullable=False,
    )
    redaction_status: Mapped[str] = mapped_column(
        String(100),
        default="redacted",
        nullable=False,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    corpus_eligibility_label: Mapped[str] = mapped_column(
        String(255),
        default="unknown",
        nullable=False,
    )
    visibility_label: Mapped[str] = mapped_column(
        String(100),
        default="invited_users",
        nullable=False,
    )
    sensitivity_class: Mapped[str] = mapped_column(
        String(100),
        default="unknown",
        nullable=False,
    )
    license_policy_label: Mapped[str] = mapped_column(
        String(100),
        default="unknown",
        nullable=False,
    )
