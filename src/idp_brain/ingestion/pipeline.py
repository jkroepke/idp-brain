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

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "source_id": self.source_id,
            "status": self.status,
            "dry_run": self.dry_run,
            "stats": self.stats,
        }


def run_ingestion(
    *,
    config_path: Path,
    source_id: str | None,
    dry_run: bool,
    operator_label: str | None = None,
    session_factory: sessionmaker[Session] | None = None,
    before_source_work: Callable[[IngestionRun], None] | None = None,
) -> list[IngestionRunResult]:
    """Record local ingestion runs for one source or all enabled sources."""

    config = load_sources_config(config_path)
    selected_sources = _select_sources(config.sources, source_id)
    config_hash = hash_config_file(config_path)
    current_session_factory = session_factory or create_session_factory()
    results: list[IngestionRunResult] = []

    with current_session_factory() as session:
        repository = IngestionRunRepository(session)
        for source in selected_sources:
            stats = empty_ingestion_counters()
            run = repository.create_started(
                IngestionRunCreate(
                    config_source_id=source.source_id,
                    requested_ref=select_requested_ref(source),
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
    source_id: str | None,
) -> list[SourceConfig]:
    if source_id is None:
        return [source for source in sources if source.enabled]

    for source in sources:
        if source.source_id == source_id:
            return [source]

    raise ValueError(f"unknown source ID: {source_id}")
