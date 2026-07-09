"""Facts, sanitized chunks, version memberships, and citations."""

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
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from idp_brain.models.base import Base, SourceProvenanceMixin, new_id, utc_now
from idp_brain.models.policy import corpus_eligibility_constraints


class Chunk(SourceProvenanceMixin, Base):
    """Retrievable sanitized text, code, or schema chunk."""

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("source_id", "chunk_key"),
        Index(
            "ix_chunks_filter_pushdown",
            "source_id",
            "source_version_id",
            "source_allowlisted",
            "visibility_label",
            "sensitivity_class",
            "license_policy_status",
            "redaction_status",
            "artifact_path",
            "language",
            "version_label",
        ),
        Index("ix_chunks_license_id", "license_id"),
        *corpus_eligibility_constraints("chunks"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    chunk_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    artifact_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("artifacts.id"),
        nullable=False,
    )
    extraction_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("artifact_extractions.id"),
    )
    sanitized_text: Mapped[str] = mapped_column(Text, nullable=False)
    sanitized_content_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    heading_path: Mapped[str | None] = mapped_column(Text)
    structure_path: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    symbol_path: Mapped[str | None] = mapped_column(String(2048))
    signature_text: Mapped[str | None] = mapped_column(Text)
    artifact_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    language: Mapped[str | None] = mapped_column(String(100))
    artifact_role: Mapped[str | None] = mapped_column(String(100))
    chunk_kind: Mapped[str | None] = mapped_column(String(100))
    token_count: Mapped[int | None] = mapped_column(Integer)
    corpus_eligibility_label: Mapped[str] = mapped_column(
        String(255),
        default="unknown",
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )


class ChunkVersion(Base):
    """Version membership and known lineage for a sanitized chunk."""

    __tablename__ = "chunk_versions"
    __table_args__ = (
        UniqueConstraint("chunk_id", "source_version_id"),
        Index(
            "ix_chunk_versions_active_version_filter",
            "chunk_id",
            "source_version_id",
            "version_label",
            "is_current",
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    chunk_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("chunks.id"),
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


class Citation(SourceProvenanceMixin, Base):
    """Stable pointer to sanitized source-backed evidence."""

    __tablename__ = "citations"
    __table_args__ = (
        UniqueConstraint("citation_key"),
        Index(
            "ix_citations_filter_pushdown",
            "source_id",
            "source_version_id",
            "source_allowlisted",
            "visibility_label",
            "sensitivity_class",
            "license_policy_status",
            "redaction_status",
            "version_label",
        ),
        Index("ix_citations_chunk_id", "chunk_id"),
        Index("ix_citations_license_id", "license_id"),
        CheckConstraint(
            "(line_start IS NULL AND line_end IS NULL) OR "
            "(line_start IS NOT NULL AND line_end IS NOT NULL "
            "AND line_start <= line_end)",
            name="line_range_order",
        ),
        *corpus_eligibility_constraints("citations"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    citation_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    artifact_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("artifacts.id"),
    )
    chunk_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("chunks.id"))
    line_start: Mapped[int | None] = mapped_column(Integer)
    line_end: Mapped[int | None] = mapped_column(Integer)
    sanitized_content_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    corpus_eligibility_label: Mapped[str] = mapped_column(
        String(255),
        default="unknown",
        nullable=False,
    )


class Fact(SourceProvenanceMixin, Base):
    """Structured fact emitted by an extractor before claim normalization."""

    __tablename__ = "facts"
    __table_args__ = (
        UniqueConstraint("source_id", "fact_key"),
        Index(
            "ix_facts_filter_pushdown",
            "source_id",
            "source_version_id",
            "source_allowlisted",
            "visibility_label",
            "sensitivity_class",
            "license_policy_status",
            "redaction_status",
            "version_label",
        ),
        Index("ix_facts_primary_citation_id", "primary_citation_id"),
        Index("ix_facts_license_id", "license_id"),
        *corpus_eligibility_constraints("facts"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    fact_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    artifact_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("artifacts.id"),
    )
    extraction_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("artifact_extractions.id"),
    )
    fact_type: Mapped[str] = mapped_column(String(100), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(1024))
    predicate: Mapped[str | None] = mapped_column(String(255))
    normalized_value: Mapped[Any | None] = mapped_column(JSON)
    value_type: Mapped[str | None] = mapped_column(String(100))
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    authority_rank: Mapped[int | None] = mapped_column(Integer)
    primary_citation_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("citations.id"),
    )
    citation_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    sanitized_content_hash: Mapped[str | None] = mapped_column(String(255))


class FactVersion(Base):
    """Version membership and known lineage for an extracted fact."""

    __tablename__ = "fact_versions"
    __table_args__ = (
        UniqueConstraint("fact_id", "source_version_id"),
        Index(
            "ix_fact_versions_active_version_filter",
            "fact_id",
            "source_version_id",
            "version_label",
            "is_current",
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_id)
    fact_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("facts.id"),
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
