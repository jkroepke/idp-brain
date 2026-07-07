"""Configured sources, resolved versions, and ingestion run records."""

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

from idp_brain.models.base import Base, TimestampMixin, new_id, utc_now
from idp_brain.models.policy import (
    CorpusEligibilityMixin,
    corpus_eligibility_constraints,
)


class Source(CorpusEligibilityMixin, TimestampMixin, Base):
    """Configured upstream source definition."""

    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("config_key"),
        Index(
            "ix_sources_filter_pushdown",
            "source_allowlisted",
            "visibility_label",
            "sensitivity_class",
            "license_policy_status",
            "redaction_status",
        ),
        Index("ix_sources_license_id", "license_id"),
        *corpus_eligibility_constraints("sources"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    config_key: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    repository_url: Mapped[str | None] = mapped_column(String(2048))
    artifact_url: Mapped[str | None] = mapped_column(String(2048))
    default_branch: Mapped[str | None] = mapped_column(String(255))
    authority_rank: Mapped[int] = mapped_column(Integer, default=100, nullable=False)


class SourceVersion(CorpusEligibilityMixin, TimestampMixin, Base):
    """Resolved upstream version, release, commit, or artifact checksum."""

    __tablename__ = "source_versions"
    __table_args__ = (
        UniqueConstraint("source_id", "version_label"),
        Index(
            "ix_source_versions_filter_pushdown",
            "source_id",
            "version_label",
            "source_allowlisted",
            "visibility_label",
            "sensitivity_class",
            "license_policy_status",
            "redaction_status",
            "is_current",
        ),
        Index("ix_source_versions_license_id", "license_id"),
        *corpus_eligibility_constraints("source_versions"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("sources.id"),
        nullable=False,
    )
    version_label: Mapped[str] = mapped_column(String(255), nullable=False)
    resolved_ref: Mapped[str | None] = mapped_column(String(255))
    repository_url: Mapped[str | None] = mapped_column(String(2048))
    artifact_url: Mapped[str | None] = mapped_column(String(2048))
    commit_sha: Mapped[str | None] = mapped_column(String(128))
    tag: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[str | None] = mapped_column(String(255))
    checksum: Mapped[str | None] = mapped_column(String(255))
    branch: Mapped[str | None] = mapped_column(String(255))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class SourceChange(TimestampMixin, Base):
    """Upstream commit, pull request, release entry, or changelog item."""

    __tablename__ = "source_changes"
    __table_args__ = (UniqueConstraint("source_id", "change_key"),)

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("sources.id"),
        nullable=False,
    )
    change_key: Mapped[str] = mapped_column(String(255), nullable=False)
    change_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(2048))
    commit_sha: Mapped[str | None] = mapped_column(String(128))
    tag: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[str | None] = mapped_column(String(255))
    checksum: Mapped[str | None] = mapped_column(String(255))
    authored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChangeVersion(Base):
    """Membership of an upstream change in a resolved source version."""

    __tablename__ = "change_versions"
    __table_args__ = (UniqueConstraint("change_id", "source_version_id"),)

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    change_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("source_changes.id"),
        nullable=False,
    )
    source_version_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("source_versions.id"),
        nullable=False,
    )
    version_label: Mapped[str | None] = mapped_column(String(255))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IngestionRun(Base):
    """One execution of the ingestion pipeline for a configured source."""

    __tablename__ = "ingestion_runs"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    source_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("sources.id"))
    source_version_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("source_versions.id"),
    )
    requested_ref: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(100), nullable=False)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
