"""Repositories for artifact candidate metadata."""

from __future__ import annotations

import hashlib

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from idp_brain.ingestion.source_snapshot import ArtifactCandidate
from idp_brain.ingestion.tombstones import ARTIFACT_REMOVED_FROM_SOURCE
from idp_brain.models import Artifact, ArtifactVersion, Source, SourceVersion
from idp_brain.models.base import utc_now


class ArtifactRepository:
    """Upsert artifact metadata without storing raw file content."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_artifact(
        self,
        *,
        source_row: Source,
        source_version: SourceVersion,
        artifact: ArtifactCandidate,
    ) -> Artifact:
        """Create or update one source-scoped artifact candidate."""

        artifact_key = artifact.path
        artifact_row = self._session.scalar(
            select(Artifact).where(
                Artifact.source_id == source_row.id,
                Artifact.artifact_key == artifact_key,
            )
        )
        if artifact_row is None:
            artifact_row = Artifact(
                id=f"artifact:{source_row.config_key}:{_stable_id(artifact_key)}",
                source_id=source_row.id,
                artifact_key=artifact_key,
                artifact_type=artifact.artifact_type,
                source_type=source_row.source_type,
            )
            self._session.add(artifact_row)

        first_containing_version_id: str | None = (
            artifact_row.first_containing_version_id
        )
        last_containing_version_id: str | None = source_version.id
        if source_row.source_type != "git_repository":
            first_containing_version_id = (
                first_containing_version_id or source_version.id
            )
        else:
            last_containing_version_id = None

        artifact_row.source_version_id = source_version.id
        artifact_row.repository_url = source_row.repository_url
        artifact_row.artifact_url = None
        artifact_row.commit_sha = artifact.commit_sha
        artifact_row.tag = artifact.tag
        artifact_row.version = artifact.version
        artifact_row.version_label = source_version.version_label
        artifact_row.checksum = artifact.checksum
        artifact_row.first_containing_version_id = first_containing_version_id
        artifact_row.last_containing_version_id = last_containing_version_id
        artifact_row.path = artifact.path
        artifact_row.logical_locator = artifact.logical_locator
        artifact_row.source_type = source_row.source_type
        artifact_row.extractor_name = None
        artifact_row.extractor_version = None
        artifact_row.extractor_profile = artifact.extractor_profile
        artifact_row.source_allowlisted = source_row.source_allowlisted
        artifact_row.visibility_label = source_row.visibility_label
        artifact_row.sensitivity_class = source_row.sensitivity_class
        artifact_row.license_policy_status = source_row.license_policy_status
        artifact_row.license_id = source_row.license_id
        artifact_row.redaction_status = source_row.redaction_status
        artifact_row.last_verified_at = utc_now()
        artifact_row.artifact_type = artifact.artifact_type
        artifact_row.artifact_role = artifact.artifact_role
        artifact_row.title = artifact.path
        artifact_row.mime_type = artifact.mime_type
        artifact_row.language = artifact.language
        artifact_row.corpus_eligibility_label = (
            artifact.corpus_eligibility_label or "unknown"
        )
        artifact_row.size_bytes = artifact.size_bytes
        artifact_row.is_generated = artifact.generated
        artifact_row.is_vendored = artifact.vendored
        artifact_row.sanitized_content_hash = None
        artifact_row.updated_at = utc_now()
        self._session.flush()
        return artifact_row

    def upsert_artifact_version(
        self,
        *,
        artifact_row: Artifact,
        source_version: SourceVersion,
    ) -> ArtifactVersion:
        """Create or update current membership for one artifact/version pair."""

        first_containing_version_id: str | None = (
            artifact_row.first_containing_version_id
        )
        last_containing_version_id: str | None = source_version.id
        if artifact_row.source_type != "git_repository":
            first_containing_version_id = (
                first_containing_version_id or source_version.id
            )
        else:
            last_containing_version_id = None
        self._session.execute(
            update(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == artifact_row.id)
            .values(is_current=False, last_verified_at=utc_now())
        )

        artifact_version = self._session.scalar(
            select(ArtifactVersion).where(
                ArtifactVersion.artifact_id == artifact_row.id,
                ArtifactVersion.source_version_id == source_version.id,
            )
        )
        if artifact_version is None:
            artifact_version = ArtifactVersion(
                id=f"artifact-version:{artifact_row.id}:{source_version.id}",
                artifact_id=artifact_row.id,
                source_version_id=source_version.id,
            )
            self._session.add(artifact_version)

        artifact_version.version_label = source_version.version_label
        artifact_version.commit_sha = artifact_row.commit_sha
        artifact_version.tag = artifact_row.tag
        artifact_version.version = artifact_row.version
        artifact_version.checksum = artifact_row.checksum
        artifact_version.first_containing_version_id = first_containing_version_id
        artifact_version.last_containing_version_id = last_containing_version_id
        artifact_version.is_current = True
        artifact_version.tombstoned_at = None
        artifact_version.tombstone_reason = None
        artifact_version.last_verified_at = utc_now()
        self._session.flush()
        return artifact_version

    def retire_artifacts_absent_from_discovery(
        self,
        *,
        source_row: Source,
        current_artifact_keys: set[str],
    ) -> int:
        """Mark artifacts absent from the discovered snapshot as non-current."""

        stale_query = (
            select(Artifact)
            .join(ArtifactVersion, ArtifactVersion.artifact_id == Artifact.id)
            .where(
                Artifact.source_id == source_row.id,
                ArtifactVersion.is_current.is_(True),
            )
        )
        if current_artifact_keys:
            stale_query = stale_query.where(
                Artifact.artifact_key.not_in(current_artifact_keys)
            )
        stale_artifacts = self._session.scalars(stale_query).all()
        if not stale_artifacts:
            return 0

        stale_artifact_ids = [artifact.id for artifact in stale_artifacts]
        tombstoned_at = utc_now()
        self._session.execute(
            update(ArtifactVersion)
            .where(ArtifactVersion.artifact_id.in_(stale_artifact_ids))
            .where(ArtifactVersion.is_current.is_(True))
            .values(
                is_current=False,
                tombstoned_at=tombstoned_at,
                tombstone_reason=ARTIFACT_REMOVED_FROM_SOURCE,
                last_verified_at=tombstoned_at,
            )
        )
        for artifact in stale_artifacts:
            artifact.source_version_id = None
            artifact.last_verified_at = utc_now()
            artifact.updated_at = utc_now()
        self._session.flush()
        return len(stale_artifacts)


def _stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]
