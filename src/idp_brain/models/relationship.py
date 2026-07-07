"""Citation-backed typed relationships between normalized entities."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from idp_brain.models.base import Base, SourceProvenanceMixin, new_id, utc_now

RELATIONSHIP_TYPES: Final[tuple[str, ...]] = (
    "contains",
    "defines",
    "references",
    "derived_from",
    "cites",
    "introduced_in",
    "removed_in",
    "changed_by",
    "conflicts_with",
)

RELATIONSHIP_TYPE_CHECK: Final[str] = "relationship_type IN ({})".format(
    ", ".join(f"'{relationship_type}'" for relationship_type in RELATIONSHIP_TYPES)
)


class Relationship(SourceProvenanceMixin, Base):
    """Typed, version-aware, citation-backed link between two entities."""

    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint("source_id", "relationship_key"),
        CheckConstraint(RELATIONSHIP_TYPE_CHECK, name="relationship_type_valid"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    relationship_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)
    from_entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    from_entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    to_entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    to_entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    authority_rank: Mapped[int | None] = mapped_column(Integer)
    primary_citation_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("citations.id"),
        nullable=False,
    )
    citation_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    sanitized_content_hash: Mapped[str | None] = mapped_column(String(255))


class RelationshipVersion(Base):
    """Version membership and known lineage for a relationship."""

    __tablename__ = "relationship_versions"
    __table_args__ = (UniqueConstraint("relationship_id", "source_version_id"),)

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    relationship_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("relationships.id"),
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
