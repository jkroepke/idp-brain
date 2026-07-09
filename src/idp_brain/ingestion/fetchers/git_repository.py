"""Git repository source fetcher."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import shutil
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path, PurePosixPath

from idp_brain.config.models import SourceConfig
from idp_brain.ingestion.git_client import GitClient
from idp_brain.ingestion.runs import sanitize_diagnostic_text
from idp_brain.ingestion.source_snapshot import (
    ArtifactCandidate,
    SourceChangeCandidate,
    SourceSnapshot,
)
from idp_brain.ingestion.version_map import git_version_label
from idp_brain.models import IngestionRun

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
GIT_CACHE_ROOT = REPOSITORY_ROOT / ".idp-brain-cache" / "ingestion" / "git"

LANGUAGE_BY_SUFFIX = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".txt": "text",
    ".py": "python",
}


class GitRepositoryConfigError(ValueError):
    """Raised for incomplete Git source configuration."""


class GitRepositoryFetcher:
    """Fetch safe Git metadata into an isolated local cache."""

    def __init__(
        self,
        *,
        config_path: Path,
        git_client: GitClient | None = None,
    ) -> None:
        self._config_path = config_path
        self._git = git_client or GitClient()

    def fetch(self, source: SourceConfig, run: IngestionRun) -> SourceSnapshot:
        """Return deterministic Git artifact and change metadata."""

        del run
        repository_url = self._resolve_repository_url(source)
        cache_path = GIT_CACHE_ROOT / _safe_cache_key(source.source_id)
        self._ensure_cache(repository_url=repository_url, cache_path=cache_path)

        resolved_refs = _resolve_refs(self._git, cache_path, source.tracked_refs)
        artifacts = tuple(
            artifact
            for resolved_ref in resolved_refs
            for artifact in _list_artifacts(
                git=self._git,
                repository=cache_path,
                source=source,
                commit_sha=resolved_ref.commit_sha,
                tag=resolved_ref.label if resolved_ref.ref_type == "tag" else None,
            )
        )
        changes = _deduplicate_changes(
            change
            for resolved_ref in resolved_refs
            for change in _list_changes(
                git=self._git,
                repository=cache_path,
                source=source,
                commit_sha=resolved_ref.commit_sha,
            )
        )
        version_label = _source_version_label(resolved_refs)
        root_identifier = _root_identifier(resolved_refs)
        snapshot_hash = _snapshot_hash(
            source=source,
            repository_url=repository_url,
            root_identifier=root_identifier,
            artifacts=artifacts,
        )
        return SourceSnapshot(
            source=source,
            root_identifier=root_identifier,
            source_version_hash=snapshot_hash,
            version_label=version_label,
            checksum=f"sha256:{snapshot_hash}",
            artifacts=artifacts,
            repository_url=repository_url,
            commit_sha=resolved_refs[0].commit_sha if len(resolved_refs) == 1 else None,
            branch=(
                resolved_refs[0].label
                if len(resolved_refs) == 1 and resolved_refs[0].ref_type == "branch"
                else None
            ),
            tag=(
                resolved_refs[0].label
                if len(resolved_refs) == 1 and resolved_refs[0].ref_type == "tag"
                else None
            ),
            version=version_label,
            changes=changes,
        )

    def _resolve_repository_url(self, source: SourceConfig) -> str:
        if source.url is None:
            raise GitRepositoryConfigError("git_repository sources require url")
        if "://" in source.url:
            return source.url
        candidate = Path(source.url)
        if not candidate.is_absolute():
            config_relative = (self._config_path.parent / candidate).resolve()
            if config_relative.exists():
                return str(config_relative)
            candidate = (REPOSITORY_ROOT / candidate).resolve()
        return str(candidate)

    def _ensure_cache(self, *, repository_url: str, cache_path: Path) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        if (cache_path / ".git").is_dir():
            cached_url = self._git.run(
                ["remote", "get-url", "origin"],
                cwd=cache_path,
                check=False,
            )
            if _normalize_repository_url(cached_url) != _normalize_repository_url(
                repository_url
            ):
                shutil.rmtree(cache_path)
                self._git.run(
                    ["clone", "--no-checkout", repository_url, str(cache_path)]
                )
                return
            self._git.run(["fetch", "--prune", "--tags", "origin"], cwd=cache_path)
            return
        self._git.run(["clone", "--no-checkout", repository_url, str(cache_path)])


class _ResolvedRef:
    def __init__(self, *, label: str, commit_sha: str, ref_type: str) -> None:
        self.label = label
        self.commit_sha = commit_sha
        self.ref_type = ref_type


def _resolve_ref(git: GitClient, repository: Path, ref_label: str) -> _ResolvedRef:
    candidates = [
        (f"refs/tags/{ref_label}", "tag"),
        (f"refs/heads/{ref_label}", "branch"),
        (f"refs/remotes/origin/{ref_label}", "branch"),
        (ref_label, "commit"),
    ]
    for candidate, ref_type in candidates:
        commit_sha = git.run(
            ["rev-parse", "--verify", f"{candidate}^{{commit}}"],
            cwd=repository,
            check=False,
        )
        if _is_commit_sha(commit_sha):
            return _ResolvedRef(
                label=ref_label,
                commit_sha=commit_sha,
                ref_type=ref_type,
            )
    raise GitRepositoryConfigError("tracked Git ref could not be resolved")


def _resolve_refs(
    git: GitClient,
    repository: Path,
    ref_labels: list[str],
) -> tuple[_ResolvedRef, ...]:
    requested_refs = ref_labels or ["HEAD"]
    return tuple(
        _resolve_ref(git, repository, ref_label) for ref_label in requested_refs
    )


def _list_artifacts(
    *,
    git: GitClient,
    repository: Path,
    source: SourceConfig,
    commit_sha: str,
    tag: str | None,
) -> tuple[ArtifactCandidate, ...]:
    output = git.run(["ls-tree", "-r", "-l", "--full-tree", commit_sha], cwd=repository)
    artifacts: list[ArtifactCandidate] = []
    for line in output.splitlines():
        if not line:
            continue
        metadata, path = line.split("\t", maxsplit=1)
        mode, object_type, object_sha, size_text = metadata.split()
        if object_type != "blob":
            continue
        del mode
        mime_type, _ = mimetypes.guess_type(path)
        suffix = PurePosixPath(path).suffix.lower()
        artifacts.append(
            ArtifactCandidate(
                path=path,
                logical_locator=f"{source.source_id}:{commit_sha[:12]}:{path}",
                checksum=f"gitblob:{object_sha}",
                size_bytes=int(size_text) if size_text != "-" else 0,
                mtime_ns=0,
                artifact_type=_artifact_type(suffix, mime_type),
                artifact_role=_artifact_role(source.extractor_profile),
                mime_type=mime_type,
                language=LANGUAGE_BY_SUFFIX.get(suffix),
                commit_sha=commit_sha,
                tag=tag,
                version=commit_sha,
            )
        )
    return tuple(sorted(artifacts, key=lambda artifact: artifact.path))


def _list_changes(
    *,
    git: GitClient,
    repository: Path,
    source: SourceConfig,
    commit_sha: str,
) -> tuple[SourceChangeCandidate, ...]:
    del source
    output = git.run(
        ["log", "--format=%H%x1f%P%x1f%aI%x1f%cI%x1f%s%x1e", commit_sha],
        cwd=repository,
    )
    changes: list[SourceChangeCandidate] = []
    for record in output.rstrip("\x1e").split("\x1e"):
        if not record.strip():
            continue
        commit, parents, authored_at, committed_at, subject = record.strip().split(
            "\x1f",
            maxsplit=4,
        )
        changes.append(
            SourceChangeCandidate(
                change_key=f"git:{commit}",
                commit_sha=commit,
                parent_shas=tuple(parent for parent in parents.split() if parent),
                authored_at=_parse_git_datetime(authored_at),
                committed_at=_parse_git_datetime(committed_at),
                sanitized_subject=_sanitize_commit_subject(subject),
            )
        )
    return tuple(changes)


def _snapshot_hash(
    *,
    source: SourceConfig,
    repository_url: str,
    root_identifier: str,
    artifacts: tuple[ArtifactCandidate, ...],
) -> str:
    payload = {
        "source_id": source.source_id,
        "repository_url": repository_url,
        "root_identifier": root_identifier,
        "include_paths": source.include_paths,
        "exclude_paths": source.exclude_paths,
        "artifacts": [
            {
                "path": artifact.path,
                "checksum": artifact.checksum,
                "size_bytes": artifact.size_bytes,
            }
            for artifact in artifacts
        ],
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _artifact_type(suffix: str, mime_type: str | None) -> str:
    if suffix in {".md", ".markdown", ".txt"}:
        return "document"
    if suffix in {".json", ".yaml", ".yml", ".toml"}:
        return "structured_data"
    if suffix in {".py", ".js", ".ts", ".go", ".rs", ".java"}:
        return "source_code"
    if mime_type is not None and mime_type.startswith("text/"):
        return "document"
    return "file"


def _artifact_role(extractor_profile: str) -> str | None:
    if "docs" in extractor_profile:
        return "documentation"
    if "source" in extractor_profile or "code" in extractor_profile:
        return "source_code"
    if "config" in extractor_profile or "schema" in extractor_profile:
        return "structured_config"
    return None


def _parse_git_datetime(value: str) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _sanitize_commit_subject(subject: str) -> str:
    return sanitize_diagnostic_text(subject)


def _safe_cache_key(source_id: str) -> str:
    safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "-", source_id).strip(".-")
    digest = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:12]
    return f"{safe_prefix[:80]}-{digest}" if safe_prefix else digest


def _is_commit_sha(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{40}", value.strip()))


def _source_version_label(resolved_refs: tuple[_ResolvedRef, ...]) -> str:
    if len(resolved_refs) == 1:
        resolved_ref = resolved_refs[0]
        return git_version_label(
            ref_label=resolved_ref.label,
            commit_sha=resolved_ref.commit_sha,
            ref_type=resolved_ref.ref_type,
        )
    payload = [
        {
            "label": resolved_ref.label,
            "commit_sha": resolved_ref.commit_sha,
            "ref_type": resolved_ref.ref_type,
        }
        for resolved_ref in resolved_refs
    ]
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"refs:{digest[:16]}"


def _root_identifier(resolved_refs: tuple[_ResolvedRef, ...]) -> str:
    if len(resolved_refs) == 1:
        return resolved_refs[0].commit_sha
    return ",".join(
        f"{resolved_ref.label}={resolved_ref.commit_sha}"
        for resolved_ref in resolved_refs
    )


def _deduplicate_changes(
    changes: Iterable[SourceChangeCandidate],
) -> tuple[SourceChangeCandidate, ...]:
    by_commit: dict[str, SourceChangeCandidate] = {}
    for change in changes:
        by_commit.setdefault(change.commit_sha, change)
    return tuple(by_commit[commit_sha] for commit_sha in sorted(by_commit))


def _normalize_repository_url(value: str) -> str:
    if value.startswith("file://"):
        return value.rstrip("/")
    path = Path(value)
    if path.is_absolute() or "://" not in value:
        return str(path.resolve())
    return value.rstrip("/")
