"""Safe source snapshot metadata produced by fetchers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from idp_brain.config.models import SourceConfig


@dataclass(frozen=True)
class ArtifactCandidate:
    """Metadata for one fetch-stage artifact candidate."""

    path: str
    logical_locator: str
    checksum: str
    size_bytes: int
    mtime_ns: int
    artifact_type: str
    artifact_role: str | None
    mime_type: str | None
    language: str | None
    corpus_eligibility_label: str | None = None
    extractor_profile: str | None = None
    included: bool = True
    skipped: bool = False
    skip_reason: str | None = None
    generated: bool = False
    vendored: bool = False
    override_reason: str | None = None
    discovery_rule_version: str | None = None
    commit_sha: str | None = None
    tag: str | None = None
    version: str | None = None


@dataclass(frozen=True)
class SkippedArtifact:
    """Sanitized fetch-stage skip diagnostic."""

    locator: str
    reason: str
    pattern: str | None = None
    included: bool = False
    skipped: bool = True
    generated: bool = False
    vendored: bool = False
    override_reason: str | None = None
    discovery_rule_version: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "locator": self.locator,
            "reason": self.reason,
        }
        if self.pattern is not None:
            payload["pattern"] = self.pattern
        if self.discovery_rule_version is not None:
            payload["included"] = self.included
            payload["skipped"] = self.skipped
            payload["generated"] = self.generated
            payload["vendored"] = self.vendored
            payload["discovery_rule_version"] = self.discovery_rule_version
            if self.override_reason is not None:
                payload["override_reason"] = self.override_reason
        return payload


@dataclass(frozen=True)
class SourceSnapshot:
    """Deterministic metadata snapshot for one configured source."""

    source: SourceConfig
    root_identifier: str
    source_version_hash: str
    version_label: str
    checksum: str
    artifacts: tuple[ArtifactCandidate, ...]
    skipped: tuple[SkippedArtifact, ...] = field(default_factory=tuple)
    repository_url: str | None = None
    commit_sha: str | None = None
    branch: str | None = None
    tag: str | None = None
    version: str | None = None
    changes: tuple[SourceChangeCandidate, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SourceChangeCandidate:
    """Sanitized Git change metadata proven by the local repository."""

    change_key: str
    commit_sha: str
    parent_shas: tuple[str, ...]
    authored_at: datetime | None
    committed_at: datetime | None
    sanitized_subject: str
