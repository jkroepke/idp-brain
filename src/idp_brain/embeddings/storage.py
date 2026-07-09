"""Persistence helpers for sanitized embedding vectors."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from idp_brain.models import Embedding
from idp_brain.models.base import utc_now


def stable_embedding_id(
    *,
    chunk_id: str,
    embedding_model_id: str,
    index_version_id: str,
    sanitized_content_hash: str,
) -> str:
    """Return a bounded deterministic ID for one vector provenance tuple."""

    payload = "\x1f".join(
        (chunk_id, embedding_model_id, index_version_id, sanitized_content_hash)
    )
    return f"embedding:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


class EmbeddingVectorRepository:
    """Upsert active vectors while preserving stale vector history."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_vector(
        self,
        *,
        chunk_id: str,
        embedding_model_id: str,
        index_version_id: str,
        sanitized_content_hash: str,
        vector: Sequence[float],
        dimensions: int,
        distance_metric: str,
    ) -> Embedding:
        """Store one active vector for a chunk/model/index/content hash."""

        now = utc_now()
        self.deactivate_stale_vectors(
            chunk_id=chunk_id,
            embedding_model_id=embedding_model_id,
            index_version_id=index_version_id,
            active_sanitized_content_hash=sanitized_content_hash,
        )
        row = self._session.scalar(
            select(Embedding).where(
                Embedding.chunk_id == chunk_id,
                Embedding.embedding_model_id == embedding_model_id,
                Embedding.index_version_id == index_version_id,
                Embedding.sanitized_content_hash == sanitized_content_hash,
            )
        )
        if row is None:
            row = Embedding(
                id=stable_embedding_id(
                    chunk_id=chunk_id,
                    embedding_model_id=embedding_model_id,
                    index_version_id=index_version_id,
                    sanitized_content_hash=sanitized_content_hash,
                ),
                chunk_id=chunk_id,
                embedding_model_id=embedding_model_id,
                index_version_id=index_version_id,
                sanitized_input_hash=sanitized_content_hash,
                sanitized_content_hash=sanitized_content_hash,
                vector=list(vector),
                dimensions=dimensions,
                distance_metric=distance_metric,
                is_active=True,
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.sanitized_input_hash = sanitized_content_hash
            row.vector = list(vector)
            row.dimensions = dimensions
            row.distance_metric = distance_metric
            row.is_active = True
            row.updated_at = now
        self._session.flush()
        return row

    def deactivate_stale_vectors(
        self,
        *,
        chunk_id: str,
        embedding_model_id: str,
        index_version_id: str,
        active_sanitized_content_hash: str | None = None,
    ) -> int:
        """Mark active vectors stale for changed or tombstoned chunks."""

        stale_rows = list(
            self._session.execute(
                select(Embedding.id, Embedding.sanitized_content_hash).where(
                    Embedding.chunk_id == chunk_id,
                    Embedding.embedding_model_id == embedding_model_id,
                    Embedding.index_version_id == index_version_id,
                    Embedding.is_active.is_(True),
                )
            )
        )
        if active_sanitized_content_hash is not None:
            stale_ids = [
                embedding_id
                for embedding_id, sanitized_content_hash in stale_rows
                if sanitized_content_hash != active_sanitized_content_hash
            ]
        else:
            stale_ids = [embedding_id for embedding_id, _ in stale_rows]
        if not stale_ids:
            return 0

        self._session.execute(
            update(Embedding)
            .where(Embedding.id.in_(stale_ids))
            .values(is_active=False, updated_at=utc_now())
        )
        self._session.flush()
        return len(stale_ids)
