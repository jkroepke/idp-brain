"""License scanner findings and policy status records."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from idp_brain.models.base import Base, TimestampMixin, new_id, utc_now
from idp_brain.models.policy import LICENSE_POLICY_STATUSES

LICENSE_FINDING_POLICY_STATUS_CHECK = "policy_status IN ({})".format(
    ", ".join(f"'{status}'" for status in LICENSE_POLICY_STATUSES)
)


class LicenseFinding(TimestampMixin, Base):
    """Scanner license metadata used by future corpus eligibility filters."""

    __tablename__ = "license_findings"
    __table_args__ = (
        Index(
            "ix_license_findings_source_version_artifact",
            "source_id",
            "source_version_id",
            "artifact_id",
        ),
        Index("ix_license_findings_policy_status", "policy_status"),
        Index("ix_license_findings_license_id", "license_id"),
        Index("ix_license_findings_citation_id", "citation_id"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="confidence_range",
        ),
        CheckConstraint(
            LICENSE_FINDING_POLICY_STATUS_CHECK, name="policy_status_valid"
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
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
    citation_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("citations.id"),
    )
    scanner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    scanner_version: Mapped[str | None] = mapped_column(String(255))
    license_expression: Mapped[str | None] = mapped_column(String(1024))
    license_id: Mapped[str | None] = mapped_column(String(100))
    copyright_notice: Mapped[str | None] = mapped_column(Text)
    finding_location: Mapped[str | None] = mapped_column(String(2048))
    confidence: Mapped[float | None] = mapped_column(Float)
    policy_status: Mapped[str] = mapped_column(
        String(100),
        default="unknown",
        nullable=False,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
