"""Discovered artifacts and extraction metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from idp_brain.models.base import (
    Base,
    SourceProvenanceMixin,
    TimestampMixin,
    new_id,
    utc_now,
)
from idp_brain.models.policy import corpus_eligibility_constraints


class Artifact(SourceProvenanceMixin, TimestampMixin, Base):
    """Discovered file, schema, spec, document, example, or generated artifact."""

    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("source_id", "artifact_key"),
        Index(
            "ix_artifacts_filter_pushdown",
            "source_id",
            "source_version_id",
            "source_allowlisted",
            "visibility_label",
            "sensitivity_class",
            "license_policy_status",
            "redaction_status",
            "path",
            "language",
            "version_label",
        ),
        Index("ix_artifacts_license_id", "license_id"),
        *corpus_eligibility_constraints("artifacts"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    artifact_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(100), nullable=False)
    artifact_role: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str | None] = mapped_column(String(100))
    corpus_eligibility_label: Mapped[str] = mapped_column(
        String(255),
        default="unknown",
        nullable=False,
    )
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    is_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_vendored: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sanitized_content_hash: Mapped[str | None] = mapped_column(String(255))


class ArtifactVersion(Base):
    """Version membership and known lineage for an artifact."""

    __tablename__ = "artifact_versions"
    __table_args__ = (
        UniqueConstraint("artifact_id", "source_version_id"),
        Index(
            "ix_artifact_versions_active_version_filter",
            "artifact_id",
            "source_version_id",
            "version_label",
            "is_current",
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    artifact_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("artifacts.id"),
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
    tombstoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tombstone_reason: Mapped[str | None] = mapped_column(String(255))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ArtifactExtraction(Base):
    """Extractor output record and diagnostics for an artifact."""

    __tablename__ = "artifact_extractions"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    artifact_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("artifacts.id"),
        nullable=False,
    )
    ingestion_run_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("ingestion_runs.id"),
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
    extractor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    extractor_version: Mapped[str | None] = mapped_column(String(255))
    extractor_profile: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(100), nullable=False)
    diagnostics: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    sanitized_content_hash: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
