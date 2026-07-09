"""Repositories for source and source version snapshot records."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from idp_brain.config.models import SourceConfig
from idp_brain.ingestion.source_snapshot import SourceSnapshot
from idp_brain.models import Source, SourceVersion
from idp_brain.models.base import utc_now


class SourceVersionRepository:
    """Upsert configured sources and deterministic source versions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_source(self, source: SourceConfig) -> Source:
        """Create or update a canonical source row from safe config metadata."""

        source_row = self._session.scalar(
            select(Source).where(Source.config_key == source.source_id)
        )
        if source_row is None:
            source_row = Source(
                id=f"source:{source.source_id}",
                config_key=source.source_id,
                name=source.source_id,
                source_type=source.source_type,
            )
            self._session.add(source_row)

        source_row.name = source.source_id
        source_row.description = None
        source_row.source_type = source.source_type
        source_row.repository_url = (
            source.url if source.source_type == "git_repository" else None
        )
        source_row.artifact_url = source.url if source.url is not None else None
        source_row.default_branch = (
            source.tracked_refs[0] if source.tracked_refs else None
        )
        source_row.authority_rank = source.source_priority
        source_row.source_allowlisted = False
        source_row.visibility_label = source.visibility_label
        source_row.sensitivity_class = source.sensitivity_class
        source_row.license_policy_status = source.license_policy
        source_row.license_id = None
        source_row.redaction_status = "unknown"
        source_row.updated_at = utc_now()
        self._session.flush()
        return source_row

    def upsert_source_version(
        self,
        *,
        source_row: Source,
        snapshot: SourceSnapshot,
    ) -> SourceVersion:
        """Create or update the deterministic version row for a snapshot."""

        source_version = self._session.scalar(
            select(SourceVersion).where(
                SourceVersion.source_id == source_row.id,
                SourceVersion.version_label == snapshot.version_label,
            )
        )
        if source_version is None:
            source_version = SourceVersion(
                id=(
                    f"source-version:{snapshot.source.source_id}:"
                    f"{snapshot.source_version_hash[:16]}"
                ),
                source_id=source_row.id,
                version_label=snapshot.version_label,
            )
            self._session.add(source_version)

        self._session.execute(
            update(SourceVersion)
            .where(SourceVersion.source_id == source_row.id)
            .values(is_current=False, updated_at=utc_now())
        )

        source_version.resolved_ref = snapshot.root_identifier
        source_version.repository_url = (
            snapshot.repository_url or source_row.repository_url
        )
        source_version.artifact_url = source_row.artifact_url
        source_version.commit_sha = snapshot.commit_sha
        source_version.tag = snapshot.tag
        source_version.version = snapshot.version
        source_version.checksum = snapshot.checksum
        source_version.branch = snapshot.branch
        source_version.is_current = True
        source_version.resolved_at = utc_now()
        source_version.source_allowlisted = source_row.source_allowlisted
        source_version.visibility_label = source_row.visibility_label
        source_version.sensitivity_class = source_row.sensitivity_class
        source_version.license_policy_status = source_row.license_policy_status
        source_version.license_id = source_row.license_id
        source_version.redaction_status = source_row.redaction_status
        source_version.updated_at = utc_now()
        self._session.flush()
        return source_version
