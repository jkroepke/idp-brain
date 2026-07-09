"""Incremental ingestion planning for fetched source snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from idp_brain.ingestion.runs import sanitize_diagnostic_text
from idp_brain.ingestion.source_snapshot import ArtifactCandidate, SourceSnapshot
from idp_brain.models import Artifact, Source


@dataclass(frozen=True)
class ArtifactIncrementalDecision:
    """Safe decision for one artifact locator in the current or previous snapshot."""

    locator: str
    status: str
    checksum: str | None
    previous_checksum: str | None = None

    def to_diagnostic(self) -> dict[str, object]:
        diagnostic: dict[str, object] = {
            "locator": sanitize_diagnostic_text(self.locator),
            "status": self.status,
        }
        if self.checksum is not None:
            diagnostic["checksum"] = self.checksum
        if self.previous_checksum is not None:
            diagnostic["previous_checksum"] = self.previous_checksum
        return diagnostic


@dataclass(frozen=True)
class IncrementalIngestionPlan:
    """Snapshot comparison outcome before extraction/redaction/chunking."""

    decisions: tuple[ArtifactIncrementalDecision, ...]

    @property
    def added_artifacts(self) -> int:
        return self._count("added")

    @property
    def changed_artifacts(self) -> int:
        return self._count("changed")

    @property
    def unchanged_artifacts(self) -> int:
        return self._count("unchanged")

    @property
    def tombstoned_artifacts(self) -> int:
        return self._count("tombstoned")

    @property
    def current_artifact_keys(self) -> set[str]:
        return {
            decision.locator
            for decision in self.decisions
            if decision.status != "tombstoned"
        }

    def diagnostics(self) -> list[dict[str, object]]:
        return [decision.to_diagnostic() for decision in self.decisions]

    def _count(self, status: str) -> int:
        return sum(1 for decision in self.decisions if decision.status == status)


def plan_incremental_ingestion(
    *,
    session: Session,
    source_row: Source,
    snapshot: SourceSnapshot,
) -> IncrementalIngestionPlan:
    """Compare a fetched snapshot with persisted artifact metadata."""

    previous_artifacts = {
        artifact.artifact_key: artifact
        for artifact in session.scalars(
            select(Artifact).where(Artifact.source_id == source_row.id)
        )
    }
    current_artifacts = {artifact.path: artifact for artifact in snapshot.artifacts}
    decisions: list[ArtifactIncrementalDecision] = []

    for locator in sorted(current_artifacts):
        current = current_artifacts[locator]
        previous = previous_artifacts.get(locator)
        decisions.append(_decision_for_current_artifact(current, previous))

    for locator in sorted(set(previous_artifacts) - set(current_artifacts)):
        previous = previous_artifacts[locator]
        if previous.source_version_id is None:
            continue
        decisions.append(
            ArtifactIncrementalDecision(
                locator=locator,
                status="tombstoned",
                checksum=None,
                previous_checksum=previous.checksum,
            )
        )

    return IncrementalIngestionPlan(decisions=tuple(decisions))


def _decision_for_current_artifact(
    current: ArtifactCandidate,
    previous: Artifact | None,
) -> ArtifactIncrementalDecision:
    if previous is None or previous.source_version_id is None:
        return ArtifactIncrementalDecision(
            locator=current.path,
            status="added",
            checksum=current.checksum,
        )
    if (
        previous.checksum == current.checksum
        and previous.extractor_profile == current.extractor_profile
        and previous.corpus_eligibility_label
        == (current.corpus_eligibility_label or "unknown")
    ):
        return ArtifactIncrementalDecision(
            locator=current.path,
            status="unchanged",
            checksum=current.checksum,
        )
    return ArtifactIncrementalDecision(
        locator=current.path,
        status="changed",
        checksum=current.checksum,
        previous_checksum=previous.checksum,
    )
