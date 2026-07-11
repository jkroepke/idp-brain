"""Sanitized bounded ingestion-run status projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, sessionmaker

from idp_brain.db import create_session_factory
from idp_brain.ingestion.runs import sanitize_diagnostic_text
from idp_brain.models import IngestionRun


@dataclass(frozen=True)
class IngestionStatus:
    run_id: str
    source_id: str
    version_ref: str | None
    profile: str | None
    status: str
    started_at: str
    finished_at: str | None
    changed_chunk_count: int
    failed_chunk_count: int
    redacted_chunk_count: int
    inactive_index_version: str | None = None
    validation_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def ingestion_status(
    *,
    run_id: str | None = None,
    source_id: str | None = None,
    limit: int = 10,
    session_factory: sessionmaker[Session] | None = None,
) -> list[IngestionStatus]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    factory = session_factory or create_session_factory()
    with factory() as session:
        statement: Select[tuple[IngestionRun]] = select(IngestionRun)
        if run_id is not None:
            statement = statement.where(IngestionRun.id == run_id)
        if source_id is not None:
            statement = statement.where(IngestionRun.config_source_id == source_id)
        rows = session.scalars(
            statement.order_by(
                IngestionRun.started_at.desc(), IngestionRun.id.asc()
            ).limit(1 if run_id else limit)
        )
        return [_projection(row) for row in rows]


def _projection(run: IngestionRun) -> IngestionStatus:
    stats = run.stats if isinstance(run.stats, dict) else {}
    return IngestionStatus(
        run_id=_safe(run.id),
        source_id=_safe(run.config_source_id or run.source_id or "[unknown]"),
        version_ref=_safe_optional(run.requested_ref),
        profile=_safe_optional(run.extractor_profile),
        status=_safe(run.status),
        started_at=_safe(run.started_at.isoformat()),
        finished_at=_safe(run.completed_at.isoformat()) if run.completed_at else None,
        changed_chunk_count=int(stats.get("changed_chunks", 0)),
        failed_chunk_count=int(stats.get("failed_artifacts", 0)),
        redacted_chunk_count=int(stats.get("redacted_candidates", 0)),
    )


def _safe(value: str) -> str:
    return sanitize_diagnostic_text(value)


def _safe_optional(value: str | None) -> str | None:
    return _safe(value) if value is not None else None
