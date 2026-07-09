"""Persistence for sanitized citations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from idp_brain.ingestion.chunking import SanitizedCitation
from idp_brain.models import Citation, SourceVersion
from idp_brain.models.base import utc_now


class CitationRepository:
    """Upsert citation rows without raw source text."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_citation(
        self,
        citation: SanitizedCitation,
        *,
        chunk_id: str,
    ) -> Citation:
        source_version = (
            self._session.get(SourceVersion, citation.source_version_id)
            if citation.source_version_id is not None
            else None
        )
        row = self._session.scalar(
            select(Citation).where(Citation.citation_key == citation.citation_key)
        )
        if row is None:
            row = Citation(id=citation.citation_key, citation_key=citation.citation_key)
            self._session.add(row)

        row.source_id = citation.source_id
        row.source_version_id = citation.source_version_id
        row.source_url = citation.source_url
        row.artifact_id = citation.artifact_id
        row.chunk_id = chunk_id
        row.line_start = (
            citation.line_range.start if citation.line_range is not None else None
        )
        row.line_end = (
            citation.line_range.end if citation.line_range is not None else None
        )
        row.sanitized_content_hash = citation.sanitized_content_hash
        row.path = citation.source_url
        row.logical_locator = citation.source_url
        row.source_type = citation.source_type
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
        row.checksum = source_version.checksum if source_version is not None else None
        row.source_allowlisted = citation.source_allowlisted
        row.visibility_label = citation.visibility_label
        row.sensitivity_class = citation.sensitivity_class
        row.corpus_eligibility_label = citation.corpus_eligibility_label
        row.license_policy_status = citation.license_policy_label
        row.license_id = citation.license_id
        row.redaction_status = citation.redaction_status
        row.last_verified_at = utc_now()
        self._session.flush()
        return row
