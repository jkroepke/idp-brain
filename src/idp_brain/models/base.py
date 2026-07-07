"""Shared SQLAlchemy declarative base and model mixins."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JsonDict = dict[str, Any]


def new_id() -> str:
    """Return a stable string identifier suitable for canonical rows."""

    return str(uuid4())


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for ORM defaults."""

    return datetime.now(UTC)


metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    """Base class for all canonical ORM models."""

    metadata = metadata


class TimestampMixin:
    """Creation and update timestamps for metadata records."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceProvenanceMixin:
    """Source-backed provenance fields required on canonical evidence rows."""

    source_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("sources.id"),
        nullable=False,
    )
    source_version_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("source_versions.id"),
    )
    repository_url: Mapped[str | None] = mapped_column(String(2048))
    artifact_url: Mapped[str | None] = mapped_column(String(2048))
    commit_sha: Mapped[str | None] = mapped_column(String(128))
    tag: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[str | None] = mapped_column(String(255))
    version_label: Mapped[str | None] = mapped_column(String(255))
    checksum: Mapped[str | None] = mapped_column(String(255))
    first_containing_version_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("source_versions.id"),
    )
    last_containing_version_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("source_versions.id"),
    )
    path: Mapped[str | None] = mapped_column(String(2048))
    logical_locator: Mapped[str | None] = mapped_column(String(2048))
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    extractor_name: Mapped[str | None] = mapped_column(String(255))
    extractor_version: Mapped[str | None] = mapped_column(String(255))
    extractor_profile: Mapped[str | None] = mapped_column(String(255))
    source_allowlisted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
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
    license_policy_status: Mapped[str] = mapped_column(
        String(100),
        default="unknown",
        nullable=False,
    )
    license_id: Mapped[str | None] = mapped_column(String(100))
    redaction_status: Mapped[str] = mapped_column(
        String(100),
        default="unknown",
        nullable=False,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
