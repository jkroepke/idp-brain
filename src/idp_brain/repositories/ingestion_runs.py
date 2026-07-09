"""Repository for durable ingestion run lifecycle records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from idp_brain.models import IngestionRun
from idp_brain.models.base import utc_now


@dataclass(frozen=True)
class IngestionRunCreate:
    """Config-derived metadata captured before source work begins."""

    config_source_id: str
    requested_ref: str | None
    config_file_hash: str
    operator_label: str | None
    extractor_profile: str
    visibility_label: str
    sensitivity_class: str
    license_policy_status: str
    corpus_eligibility_label: str
    stats: Mapping[str, int]


class IngestionRunRepository:
    """Write ingestion run rows with explicit lifecycle updates."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_started(self, payload: IngestionRunCreate) -> IngestionRun:
        """Insert and flush a started run before source work begins."""

        run = IngestionRun(
            config_source_id=payload.config_source_id,
            requested_ref=payload.requested_ref,
            config_file_hash=payload.config_file_hash,
            operator_label=payload.operator_label,
            extractor_profile=payload.extractor_profile,
            visibility_label=payload.visibility_label,
            sensitivity_class=payload.sensitivity_class,
            license_policy_status=payload.license_policy_status,
            corpus_eligibility_label=payload.corpus_eligibility_label,
            status="started",
            stats=dict(payload.stats),
            diagnostics={},
            started_at=utc_now(),
        )
        self._session.add(run)
        self._session.flush()
        return run

    def update_status(
        self,
        run: IngestionRun,
        status: str,
        *,
        stats: Mapping[str, int] | None = None,
        diagnostics: Mapping[str, Any] | None = None,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> IngestionRun:
        """Update lifecycle state and flush immediately."""

        run.status = status
        if stats is not None:
            run.stats = dict(stats)
        if diagnostics is not None:
            run.diagnostics = dict(diagnostics)
        if error_message is not None:
            run.error_message = error_message
        if completed_at is not None:
            run.completed_at = completed_at
        self._session.flush()
        return run
