"""Normalized claims and preserved claim conflicts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from idp_brain.models.base import Base, SourceProvenanceMixin, new_id, utc_now


class Claim(SourceProvenanceMixin, Base):
    """Normalized subject/predicate/value statement backed by citations."""

    __tablename__ = "claims"
    __table_args__ = (
        UniqueConstraint("source_id", "claim_key"),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="confidence_range",
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    claim_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    fact_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("facts.id"))
    subject: Mapped[str] = mapped_column(String(1024), nullable=False)
    predicate: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[Any] = mapped_column(JSON, nullable=False)
    value_type: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    authority_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    primary_citation_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("citations.id"),
        nullable=False,
    )
    citation_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    sanitized_content_hash: Mapped[str | None] = mapped_column(String(255))


class ClaimVersion(Base):
    """Version membership and known lineage for a normalized claim."""

    __tablename__ = "claim_versions"
    __table_args__ = (UniqueConstraint("claim_id", "source_version_id"),)

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    claim_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("claims.id"),
        nullable=False,
    )
    source_version_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("source_versions.id"),
        nullable=False,
    )
    version_label: Mapped[str | None] = mapped_column(String(255))
    commit_sha: Mapped[str | None] = mapped_column(String(128))
    tag: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[str | None] = mapped_column(String(255))
    checksum: Mapped[str | None] = mapped_column(String(255))
    first_containing_version_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("source_versions.id"),
    )
    last_containing_version_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("source_versions.id"),
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClaimConflict(Base):
    """Detected incompatible claims with competing evidence preserved."""

    __tablename__ = "claim_conflicts"
    __table_args__ = (
        UniqueConstraint("conflict_key"),
        CheckConstraint("left_claim_id <> right_claim_id", name="different_claims"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    conflict_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    left_claim_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("claims.id"),
        nullable=False,
    )
    right_claim_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("claims.id"),
        nullable=False,
    )
    primary_citation_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("citations.id"),
        nullable=False,
    )
    overlap_scope: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    evidence_citation_ids: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(100),
        default="unresolved",
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
