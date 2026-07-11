"""Minimal ingestion run orchestration through local directory snapshotting."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from idp_brain.config import load_sources_config
from idp_brain.config.models import SourceConfig
from idp_brain.db import create_session_factory
from idp_brain.ingestion.discovery import ArtifactDiscoveryService
from idp_brain.ingestion.fetchers import GitRepositoryFetcher, LocalDirectoryFetcher
from idp_brain.ingestion.git_client import GitCommandError
from idp_brain.ingestion.incremental import plan_incremental_ingestion
from idp_brain.ingestion.runs import (
    SAFE_ERROR_MESSAGE,
    hash_config_file,
    sanitized_failure_diagnostic,
    select_requested_ref,
)
from idp_brain.ingestion.source_snapshot import ArtifactCandidate, SourceSnapshot
from idp_brain.models import IngestionRun, IngestionRunStatus, empty_ingestion_counters
from idp_brain.models.base import utc_now
from idp_brain.repositories.artifacts import ArtifactRepository
from idp_brain.repositories.ingestion_runs import (
    IngestionRunCreate,
    IngestionRunRepository,
)
from idp_brain.repositories.source_changes import SourceChangeRepository
from idp_brain.repositories.source_versions import SourceVersionRepository


class IngestionStageNotImplementedError(RuntimeError):
    """Raised when a later ingestion stage is requested before it exists."""


@dataclass(frozen=True)
class IngestionRunResult:
    """Stable CLI projection for a recorded ingestion run."""

    run_id: str
    source_id: str
    status: str
    dry_run: bool
    stats: dict[str, int]
    requested_ref: str | None = None
    extractor_profile: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    inactive_index_version: str | None = None
    validation_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "source_id": self.source_id,
            "status": self.status,
            "dry_run": self.dry_run,
            "stats": self.stats,
            "version_ref": self.requested_ref,
            "profile": self.extractor_profile,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "inactive_index_version": self.inactive_index_version,
            "validation_only": self.validation_only,
        }


def run_ingestion(
    *,
    config_path: Path,
    source_id: str | None,
    source_ids: tuple[str, ...] | None = None,
    requested_version: str | None = None,
    profile_override: str | None = None,
    dry_run: bool,
    operator_label: str | None = None,
    session_factory: sessionmaker[Session] | None = None,
    before_source_work: Callable[[IngestionRun], None] | None = None,
) -> list[IngestionRunResult]:
    """Record local ingestion runs for one source or all enabled sources."""

    config = load_sources_config(config_path)
    requested_ids = source_ids or ((source_id,) if source_id is not None else ())
    selected_sources = _select_sources(
        config.sources,
        requested_ids,
        enforce_enabled=source_ids is not None,
    )
    config_hash = hash_config_file(config_path)
    current_session_factory = session_factory or create_session_factory()
    results: list[IngestionRunResult] = []

    with current_session_factory() as session:
        repository = IngestionRunRepository(session)
        for source in selected_sources:
            if (
                profile_override is not None
                and profile_override != source.extractor_profile
            ):
                raise ValueError(
                    f"profile {profile_override!r} is not configured for source "
                    f"{source.source_id!r}"
                )
            stats = empty_ingestion_counters()
            run = repository.create_started(
                IngestionRunCreate(
                    config_source_id=source.source_id,
                    requested_ref=requested_version or select_requested_ref(source),
                    config_file_hash=config_hash,
                    operator_label=operator_label,
                    extractor_profile=source.extractor_profile,
                    visibility_label=source.visibility_label,
                    sensitivity_class=source.sensitivity_class,
                    license_policy_status=source.license_policy,
                    corpus_eligibility_label=source.corpus_eligibility,
                    stats=stats,
                )
            )
            session.commit()

            try:
                if before_source_work is not None:
                    before_source_work(run)
                if not dry_run:
                    if source.source_type not in {"git_repository", "local_directory"}:
                        raise IngestionStageNotImplementedError(
                            "source fetching is implemented in later MVP steps"
                        )
                    repository.update_status(
                        run,
                        IngestionRunStatus.fetching.value,
                        stats=stats,
                    )
                    session.commit()
                    snapshot = _fetch_source_snapshot(
                        config_path=config_path,
                        source=source,
                        run=run,
                    )
                    stats["fetched_artifacts"] = len(snapshot.artifacts)
                    repository.update_status(
                        run,
                        IngestionRunStatus.discovering.value,
                        stats=stats,
                    )
                    session.commit()
                    snapshot = ArtifactDiscoveryService(
                        config_path=config_path
                    ).discover(snapshot)
                    source_repository = SourceVersionRepository(session)
                    artifact_repository = ArtifactRepository(session)
                    change_repository = SourceChangeRepository(session)
                    source_row = source_repository.upsert_source(source)
                    incremental_plan = plan_incremental_ingestion(
                        session=session,
                        source_row=source_row,
                        snapshot=snapshot,
                    )
                    source_version = source_repository.upsert_source_version(
                        source_row=source_row,
                        snapshot=snapshot,
                    )
                    for artifact in snapshot.artifacts:
                        artifact_row = artifact_repository.upsert_artifact(
                            source_row=source_row,
                            source_version=source_version,
                            artifact=artifact,
                        )
                        artifact_repository.upsert_artifact_version(
                            artifact_row=artifact_row,
                            source_version=source_version,
                        )
                    retire_absent = (
                        artifact_repository.retire_artifacts_absent_from_discovery
                    )
                    tombstoned_artifacts = retire_absent(
                        source_row=source_row,
                        current_artifact_keys=incremental_plan.current_artifact_keys,
                    )
                    stats["added_artifacts"] = incremental_plan.added_artifacts
                    stats["changed_artifacts"] = incremental_plan.changed_artifacts
                    stats["unchanged_artifacts"] = incremental_plan.unchanged_artifacts
                    stats["tombstoned_artifacts"] = tombstoned_artifacts
                    stats["tombstoned_records"] = tombstoned_artifacts
                    for change in snapshot.changes:
                        change_row = change_repository.upsert_change(
                            source_row=source_row,
                            source_version=source_version,
                            change=change,
                        )
                        change_repository.upsert_change_version(
                            change_row=change_row,
                            source_version=source_version,
                        )
                    stats["discovered_artifacts"] = len(snapshot.artifacts)
                    stats["skipped_generated_files"] = sum(
                        1 for skipped in snapshot.skipped if skipped.generated
                    )
                    stats["skipped_vendored_files"] = sum(
                        1 for skipped in snapshot.skipped if skipped.vendored
                    )
                    run.source_id = source_row.id
                    run.source_version_id = source_version.id
                    run.diagnostics = {
                        "source_version": source_version.version_label,
                        "included_artifacts": [
                            _included_artifact_diagnostic(artifact)
                            for artifact in snapshot.artifacts
                            if artifact.override_reason is not None
                        ],
                        "skipped_artifacts": [
                            skipped.to_dict() for skipped in snapshot.skipped
                        ],
                        "incremental_artifacts": incremental_plan.diagnostics(),
                    }
                repository.update_status(
                    run,
                    IngestionRunStatus.completed.value,
                    stats=stats,
                    completed_at=utc_now(),
                )
                session.commit()
            except Exception as exc:
                run_id = run.id
                session.rollback()
                failed_run = session.get(IngestionRun, run_id)
                if failed_run is None:
                    raise
                diagnostics = sanitized_failure_diagnostic(
                    error=exc,
                    stage=failed_run.status,
                    source_id=source.source_id,
                    retryable=isinstance(exc, GitCommandError),
                )
                repository.update_status(
                    failed_run,
                    IngestionRunStatus.failed.value,
                    diagnostics=diagnostics,
                    error_message=SAFE_ERROR_MESSAGE,
                    completed_at=utc_now(),
                )
                session.commit()
                run = failed_run
                raise

            results.append(
                IngestionRunResult(
                    run_id=run.id,
                    source_id=source.source_id,
                    status=run.status,
                    dry_run=dry_run,
                    stats=dict(run.stats),
                    requested_ref=run.requested_ref,
                    extractor_profile=run.extractor_profile,
                    started_at=run.started_at.isoformat(),
                    finished_at=run.completed_at.isoformat()
                    if run.completed_at
                    else None,
                )
            )

    return results


def _included_artifact_diagnostic(artifact: ArtifactCandidate) -> dict[str, object]:
    return {
        "locator": artifact.path,
        "included": True,
        "skipped": False,
        "generated": artifact.generated,
        "vendored": artifact.vendored,
        "override_reason": artifact.override_reason,
        "discovery_rule_version": artifact.discovery_rule_version,
    }


def _fetch_source_snapshot(
    *,
    config_path: Path,
    source: SourceConfig,
    run: IngestionRun,
) -> SourceSnapshot:
    if source.source_type == "git_repository":
        return GitRepositoryFetcher(config_path=config_path).fetch(source, run)
    return LocalDirectoryFetcher(config_path=config_path).fetch(source, run)


def _select_sources(
    sources: list[SourceConfig],
    source_ids: tuple[str, ...],
    *,
    enforce_enabled: bool = True,
) -> list[SourceConfig]:
    if not source_ids:
        return [source for source in sources if source.enabled]
    by_id = {source.source_id: source for source in sources}
    unknown = [source_id for source_id in source_ids if source_id not in by_id]
    if unknown:
        raise ValueError("requested source is unavailable")
    if enforce_enabled and any(
        not by_id[source_id].enabled for source_id in source_ids
    ):
        raise ValueError("requested source is unavailable")
    return [by_id[source_id] for source_id in dict.fromkeys(source_ids)]
