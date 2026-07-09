"""Persistence for sanitized chunks and version memberships."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from idp_brain.ingestion.chunking import SanitizedChunk
from idp_brain.ingestion.tombstones import CHUNK_REMOVED_FROM_SOURCE
from idp_brain.models import Chunk, ChunkVersion, SourceVersion
from idp_brain.models.base import utc_now


class ChunkRepository:
    """Upsert sanitized chunk rows without embeddings or search indexes."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_chunk(self, chunk: SanitizedChunk) -> Chunk:
        source_version = (
            self._session.get(SourceVersion, chunk.source_version_id)
            if chunk.source_version_id is not None
            else None
        )
        row = self._session.scalar(
            select(Chunk).where(
                Chunk.source_id == chunk.source_id,
                Chunk.chunk_key == chunk.chunk_key,
            )
        )
        if row is None:
            row = Chunk(id=chunk.chunk_key, chunk_key=chunk.chunk_key)
            self._session.add(row)

        row.artifact_id = chunk.artifact_id
        row.extraction_id = chunk.extraction_id
        row.source_id = chunk.source_id
        row.source_version_id = chunk.source_version_id
        row.repository_url = (
            source_version.repository_url if source_version is not None else None
        )
        row.artifact_url = (
            source_version.artifact_url if source_version is not None else None
        )
        row.commit_sha = (
            source_version.commit_sha if source_version is not None else None
        )
        row.tag = source_version.tag if source_version is not None else None
        row.version = source_version.version if source_version is not None else None
        row.version_label = (
            source_version.version_label if source_version is not None else None
        )
        row.checksum = chunk.sanitized_content_hash
        row.sanitized_text = chunk.sanitized_text
        row.sanitized_content_hash = chunk.sanitized_content_hash
        row.heading_path = chunk.heading_path
        row.structure_path = list(chunk.structure_path)
        row.symbol_path = chunk.symbol_path
        row.signature_text = chunk.signature_text
        row.artifact_path = chunk.artifact_path
        row.language = chunk.language
        row.artifact_role = chunk.artifact_role
        row.chunk_kind = chunk.chunk_kind
        row.token_count = chunk.token_count
        row.corpus_eligibility_label = chunk.corpus_eligibility_label
        row.metadata_ = chunk.metadata
        row.path = chunk.artifact_path
        row.logical_locator = chunk.logical_locator
        row.source_type = chunk.source_type
        row.extractor_profile = chunk.chunker_profile
        row.source_allowlisted = chunk.source_allowlisted
        row.visibility_label = chunk.visibility_label
        row.sensitivity_class = chunk.sensitivity_class
        row.license_policy_status = chunk.license_policy_label
        row.license_id = chunk.license_id
        row.redaction_status = chunk.redaction_status
        row.last_verified_at = utc_now()
        self._session.flush()
        return row

    def upsert_chunk_version(self, *, chunk_row: Chunk) -> ChunkVersion | None:
        if chunk_row.source_version_id is None:
            return None
        self._session.execute(
            update(ChunkVersion)
            .where(ChunkVersion.chunk_id == chunk_row.id)
            .values(is_current=False, last_verified_at=utc_now())
        )
        source_version = self._session.get(SourceVersion, chunk_row.source_version_id)
        row = self._session.scalar(
            select(ChunkVersion).where(
                ChunkVersion.chunk_id == chunk_row.id,
                ChunkVersion.source_version_id == chunk_row.source_version_id,
            )
        )
        if row is None:
            row = ChunkVersion(
                id=f"chunk-version:{chunk_row.id}:{chunk_row.source_version_id}",
                chunk_id=chunk_row.id,
                source_version_id=chunk_row.source_version_id,
            )
            self._session.add(row)

        row.version_label = (
            source_version.version_label if source_version is not None else None
        )
        row.commit_sha = chunk_row.commit_sha
        row.tag = chunk_row.tag
        row.version = chunk_row.version
        row.checksum = chunk_row.sanitized_content_hash
        row.first_containing_version_id = chunk_row.first_containing_version_id
        row.last_containing_version_id = chunk_row.last_containing_version_id
        row.is_current = True
        row.tombstoned_at = None
        row.tombstone_reason = None
        row.last_verified_at = utc_now()
        self._session.flush()
        return row

    def retire_chunks_absent_from_snapshot(
        self,
        *,
        source_id: str,
        current_chunk_keys: set[str],
    ) -> int:
        """Tombstone current chunk memberships absent from a sanitized snapshot."""

        stale_query = (
            select(Chunk)
            .join(ChunkVersion, ChunkVersion.chunk_id == Chunk.id)
            .where(
                Chunk.source_id == source_id,
                ChunkVersion.is_current.is_(True),
            )
        )
        if current_chunk_keys:
            stale_query = stale_query.where(Chunk.chunk_key.not_in(current_chunk_keys))
        stale_chunks = self._session.scalars(stale_query).all()
        if not stale_chunks:
            return 0

        tombstoned_at = utc_now()
        stale_chunk_ids = [chunk.id for chunk in stale_chunks]
        self._session.execute(
            update(ChunkVersion)
            .where(ChunkVersion.chunk_id.in_(stale_chunk_ids))
            .where(ChunkVersion.is_current.is_(True))
            .values(
                is_current=False,
                tombstoned_at=tombstoned_at,
                tombstone_reason=CHUNK_REMOVED_FROM_SOURCE,
                last_verified_at=tombstoned_at,
            )
        )
        for chunk in stale_chunks:
            chunk.source_version_id = None
            chunk.last_verified_at = tombstoned_at
        self._session.flush()
        return len(stale_chunks)
