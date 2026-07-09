"""Persistence for safe license policy finding metadata."""

from __future__ import annotations

from sqlalchemy.orm import Session

from idp_brain.ingestion.redaction_stage import SanitizedExtractionCandidate
from idp_brain.models import LicenseFinding


class LicenseFindingRepository:
    """Write license policy findings without full raw artifact content."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_for_candidate(
        self,
        candidate: SanitizedExtractionCandidate,
    ) -> LicenseFinding:
        original = candidate.original
        finding = candidate.license_finding
        row = LicenseFinding(
            source_id=original.source_id or "",
            source_version_id=original.source_version_id,
            artifact_id=original.artifact_id or "",
            scanner_name=finding.scanner_name,
            scanner_version=finding.scanner_version,
            license_expression=finding.license_expression,
            license_id=finding.license_id,
            copyright_notice=finding.copyright_notice,
            finding_location=finding.finding_location,
            confidence=finding.confidence,
            policy_status=finding.policy_status,
            corpus_eligibility_label=candidate.corpus_eligibility_label,
            visibility_label=candidate.visibility_label,
            sensitivity_class=candidate.sensitivity_class,
            license_policy_label=candidate.license_policy_label,
        )
        self._session.add(row)
        self._session.flush()
        return row
