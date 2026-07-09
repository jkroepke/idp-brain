"""Safe metadata persistence for artifact extraction attempts."""

from __future__ import annotations

from sqlalchemy.orm import Session

from idp_brain.ingestion.extractors import ExtractionResult
from idp_brain.ingestion.redaction_stage import (
    SanitizedExtractionResult,
    UnredactedCandidateError,
)
from idp_brain.models import ArtifactExtraction
from idp_brain.models.base import utc_now


class ArtifactExtractionRepository:
    """Write extraction metadata without raw extracted candidate text."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_from_result(
        self,
        result: ExtractionResult,
        *,
        ingestion_run_id: str | None,
        sanitized_content_hash: str | None = None,
    ) -> ArtifactExtraction:
        if result.candidates:
            raise UnredactedCandidateError(
                "extraction candidates must pass redaction before persistence"
            )
        artifact = result.artifact
        row = ArtifactExtraction(
            artifact_id=artifact.artifact_id,
            ingestion_run_id=ingestion_run_id,
            source_id=artifact.source_id,
            source_version_id=artifact.source_version_id,
            extractor_name=result.extractor_name,
            extractor_version=result.extractor_version,
            extractor_profile=artifact.extractor_profile,
            status=result.status,
            diagnostics=result.safe_summary(),
            sanitized_content_hash=sanitized_content_hash,
            completed_at=utc_now(),
        )
        self._session.add(row)
        self._session.flush()
        return row

    def create_from_sanitized_result(
        self,
        result: SanitizedExtractionResult,
        *,
        ingestion_run_id: str | None,
    ) -> ArtifactExtraction:
        for candidate in result.candidates:
            if candidate.redaction_status not in {"redacted", "redaction_checked"}:
                raise UnredactedCandidateError(
                    "candidate must be redacted or redaction_checked before persistence"
                )
        artifact = result.artifact
        row = ArtifactExtraction(
            artifact_id=artifact.artifact_id,
            ingestion_run_id=ingestion_run_id,
            source_id=artifact.source_id,
            source_version_id=artifact.source_version_id,
            extractor_name=result.extractor_name,
            extractor_version=result.extractor_version,
            extractor_profile=artifact.extractor_profile,
            status=result.status,
            diagnostics=result.safe_summary(),
            sanitized_content_hash=_combined_sanitized_hash(result),
            completed_at=utc_now(),
        )
        self._session.add(row)
        self._session.flush()
        return row


def _combined_sanitized_hash(result: SanitizedExtractionResult) -> str | None:
    hashes = [
        candidate.sanitized_content_hash
        for candidate in result.candidates
        if candidate.sanitized_content_hash is not None
    ]
    if not hashes:
        return None
    import hashlib

    return "sha256:" + hashlib.sha256("\n".join(hashes).encode("utf-8")).hexdigest()
