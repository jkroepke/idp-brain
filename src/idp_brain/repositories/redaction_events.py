"""Persistence for sanitized redaction event metadata."""

from __future__ import annotations

from sqlalchemy.orm import Session

from idp_brain.ingestion.redaction_stage import SanitizedExtractionCandidate
from idp_brain.ingestion.runs import sanitize_diagnostic_text
from idp_brain.models import RedactionEvent


class RedactionEventRepository:
    """Write redaction findings without matched values or raw context."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_for_candidate(
        self,
        candidate: SanitizedExtractionCandidate,
        *,
        ingestion_run_id: str,
    ) -> list[RedactionEvent]:
        rows: list[RedactionEvent] = []
        original = candidate.original
        for finding in candidate.redaction_findings:
            row = RedactionEvent(
                ingestion_run_id=ingestion_run_id,
                source_id=original.source_id or "",
                source_version_id=original.source_version_id,
                artifact_id=original.artifact_id or "",
                detector_name=finding.scanner_name,
                detector_version=finding.scanner_version,
                rule_id=finding.rule_id,
                redaction_type=finding.redaction_type,
                marker=finding.marker,
                match_count=finding.count,
                confidence=finding.confidence,
                location_locator=sanitize_diagnostic_text(original.locator),
                sanitized_content_hash=candidate.sanitized_content_hash,
                redaction_profile="mvp-default",
                severity=finding.severity,
                redaction_status=candidate.redaction_status,
                corpus_eligibility_label=candidate.corpus_eligibility_label,
                visibility_label=candidate.visibility_label,
                sensitivity_class=candidate.sensitivity_class,
                license_policy_label=candidate.license_policy_label,
            )
            self._session.add(row)
            rows.append(row)
        self._session.flush()
        return rows
