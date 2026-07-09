"""Mandatory redaction stage between extraction and persisted content."""

from __future__ import annotations

from dataclasses import dataclass, replace

from idp_brain.config.models import SecurityConfig
from idp_brain.ingestion.extractors import (
    ArtifactExtractionContext,
    ExtractionCandidate,
    ExtractionResult,
)
from idp_brain.ingestion.extractors.base import safe_content_hash
from idp_brain.security import (
    LicensePolicyFinding,
    RedactionFinding,
    Redactor,
    classify_license_policy,
    classify_sanitized_candidate,
)

REDACTION_SCHEMA_VERSION = "redacted-extractor-candidates-v1"
SAFE_REDACTION_STATUSES = {"redacted", "redaction_checked"}


class UnredactedCandidateError(ValueError):
    """Raised when unredacted candidate text reaches a persistence boundary."""


@dataclass(frozen=True)
class SanitizedExtractionCandidate:
    """Redacted candidate text plus safe policy/provenance labels."""

    original: ExtractionCandidate
    sanitized_text: str | None
    redaction_status: str
    sensitivity_class: str
    visibility_label: str
    license_policy_label: str
    corpus_eligibility_label: str
    sanitized_content_hash: str | None
    redaction_findings: tuple[RedactionFinding, ...]
    license_finding: LicensePolicyFinding

    def safe_metadata(self) -> dict[str, object]:
        payload = self.original.safe_metadata()
        payload["redaction_status"] = self.redaction_status
        payload["sanitized_content_hash"] = self.sanitized_content_hash
        payload["redaction_findings"] = [
            {
                "rule_id": finding.rule_id,
                "redaction_type": finding.redaction_type,
                "marker": finding.marker,
                "count": finding.count,
                "confidence": finding.confidence,
                "scanner_name": finding.scanner_name,
                "scanner_version": finding.scanner_version,
                "severity": finding.severity,
            }
            for finding in self.redaction_findings
        ]
        payload["license_policy_status"] = self.license_finding.policy_status
        payload["license_id"] = self.license_finding.license_id
        return payload


@dataclass(frozen=True)
class SanitizedExtractionResult:
    """Extractor output after mandatory redaction and policy classification."""

    extraction: ExtractionResult
    candidates: tuple[SanitizedExtractionCandidate, ...]

    @property
    def artifact(self) -> ArtifactExtractionContext:
        return self.extraction.artifact

    @property
    def extractor_name(self) -> str:
        return self.extraction.extractor_name

    @property
    def extractor_version(self) -> str:
        return self.extraction.extractor_version

    @property
    def status(self) -> str:
        return self.extraction.status

    def safe_summary(self) -> dict[str, object]:
        counts: dict[str, int] = {}
        for candidate in self.candidates:
            counts[candidate.original.candidate_type] = (
                counts.get(candidate.original.candidate_type, 0) + 1
            )
        return {
            "schema_version": REDACTION_SCHEMA_VERSION,
            "candidate_count": len(self.candidates),
            "candidate_counts": counts,
            "diagnostics": [
                diagnostic.to_dict() for diagnostic in self.extraction.diagnostics
            ],
            "redaction_events": sum(
                len(candidate.redaction_findings) for candidate in self.candidates
            ),
            "redaction_statuses": sorted(
                {candidate.redaction_status for candidate in self.candidates}
            ),
        }


class RedactionStage:
    """Redact every extraction candidate before later persistence or chunking."""

    def __init__(self, security_config: SecurityConfig | None = None) -> None:
        self._security_config = security_config

    def redact(self, result: ExtractionResult) -> SanitizedExtractionResult:
        sanitized_candidates = tuple(
            self._redact_candidate(candidate) for candidate in result.candidates
        )
        return SanitizedExtractionResult(
            extraction=result,
            candidates=sanitized_candidates,
        )

    def _redact_candidate(
        self,
        candidate: ExtractionCandidate,
    ) -> SanitizedExtractionCandidate:
        pii_required = candidate.sensitivity_class in {"confidential", "restricted"}
        redactor = Redactor.from_security_config(
            self._security_config,
            pii_required=pii_required,
        )
        sanitized_text, findings = redactor.redact(candidate.text)
        sensitivity_class = classify_sanitized_candidate(
            existing_sensitivity_class=candidate.sensitivity_class or "unknown",
            findings=findings,
        )
        redaction_status = "redacted" if findings else "redaction_checked"
        license_finding = classify_license_policy(
            text=sanitized_text,
            configured_policy_status=candidate.license_policy_label or "unknown",
            locator=candidate.locator,
        )
        return SanitizedExtractionCandidate(
            original=replace(
                candidate,
                sensitivity_class=sensitivity_class,
                license_policy_label=license_finding.policy_status,
            ),
            sanitized_text=sanitized_text,
            redaction_status=redaction_status,
            sensitivity_class=sensitivity_class,
            visibility_label=candidate.visibility_label or "invited_users",
            license_policy_label=license_finding.policy_status,
            corpus_eligibility_label=candidate.corpus_eligibility_label or "unknown",
            sanitized_content_hash=(
                safe_content_hash(sanitized_text)
                if sanitized_text is not None
                else None
            ),
            redaction_findings=findings,
            license_finding=license_finding,
        )


def assert_candidate_redacted(candidate: SanitizedExtractionCandidate) -> None:
    """Reject candidates that have not passed through redaction."""

    if candidate.redaction_status not in SAFE_REDACTION_STATUSES:
        raise UnredactedCandidateError(
            "candidate must be redacted or redaction_checked before persistence"
        )
