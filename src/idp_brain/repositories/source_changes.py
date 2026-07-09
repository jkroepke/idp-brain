"""Repositories for sanitized source change provenance."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from idp_brain.ingestion.source_snapshot import SourceChangeCandidate
from idp_brain.models import ChangeVersion, Source, SourceChange, SourceVersion
from idp_brain.models.base import utc_now


class SourceChangeRepository:
    """Upsert Git commit provenance without raw diffs or commit bodies."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_change(
        self,
        *,
        source_row: Source,
        source_version: SourceVersion,
        change: SourceChangeCandidate,
    ) -> SourceChange:
        """Create or update one sanitized source change row."""

        change_row = self._session.scalar(
            select(SourceChange).where(
                SourceChange.source_id == source_row.id,
                SourceChange.change_key == change.change_key,
            )
        )
        if change_row is None:
            change_row = SourceChange(
                id=f"source-change:{source_row.config_key}:{change.commit_sha[:16]}",
                source_id=source_row.id,
                change_key=change.change_key,
                change_type="git_commit",
            )
            self._session.add(change_row)

        change_row.source_version_id = source_version.id
        change_row.title = change.sanitized_subject
        change_row.url = None
        change_row.commit_sha = change.commit_sha
        change_row.parent_shas = list(change.parent_shas)
        change_row.tag = source_version.tag
        change_row.version = source_version.version_label
        change_row.checksum = None
        change_row.authored_at = change.authored_at
        change_row.committed_at = change.committed_at
        change_row.merged_at = None
        change_row.source_allowlisted = source_row.source_allowlisted
        change_row.visibility_label = source_row.visibility_label
        change_row.sensitivity_class = source_row.sensitivity_class
        change_row.license_policy_status = source_row.license_policy_status
        change_row.license_id = source_row.license_id
        change_row.redaction_status = source_row.redaction_status
        change_row.updated_at = utc_now()
        self._session.flush()
        return change_row

    def upsert_change_version(
        self,
        *,
        change_row: SourceChange,
        source_version: SourceVersion,
    ) -> ChangeVersion:
        """Create or update change membership in a resolved source version."""

        change_version = self._session.scalar(
            select(ChangeVersion).where(
                ChangeVersion.change_id == change_row.id,
                ChangeVersion.source_version_id == source_version.id,
            )
        )
        if change_version is None:
            change_version = ChangeVersion(
                id=f"change-version:{change_row.id}:{source_version.id}",
                change_id=change_row.id,
                source_version_id=source_version.id,
            )
            self._session.add(change_version)

        change_version.version_label = source_version.version_label
        change_version.last_verified_at = utc_now()
        self._session.flush()
        return change_version
