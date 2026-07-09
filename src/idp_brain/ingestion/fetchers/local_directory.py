"""Deterministic local directory source fetcher."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath

from idp_brain.config.models import SourceConfig
from idp_brain.ingestion.source_snapshot import (
    ArtifactCandidate,
    SourceSnapshot,
)
from idp_brain.models import IngestionRun

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_ALLOWLIST_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "local_directory"
ALLOWLIST_ENV_VAR = "IDP_BRAIN_LOCAL_SOURCE_ALLOWLIST"

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


class LocalDirectoryPathError(ValueError):
    """Raised for unsafe local directory source paths."""


class LocalDirectoryFetcher:
    """Build a safe metadata snapshot for a configured local directory."""

    def __init__(self, *, config_path: Path) -> None:
        self._config_path = config_path

    def fetch(self, source: SourceConfig, run: IngestionRun) -> SourceSnapshot:
        """Return local artifact metadata in deterministic path order."""

        del run
        root = self._resolve_local_root(source)
        if not root.is_dir():
            raise LocalDirectoryPathError("local_directory path must be a directory")

        artifacts: list[ArtifactCandidate] = []
        for file_path in sorted(path for path in root.rglob("*") if path.is_file()):
            relative_path = _relative_posix(file_path, root)
            stat = file_path.stat()
            checksum = _file_sha256(file_path)
            mime_type, _ = mimetypes.guess_type(relative_path)
            suffix = PurePosixPath(relative_path).suffix.lower()
            artifacts.append(
                ArtifactCandidate(
                    path=relative_path,
                    logical_locator=f"{source.source_id}:{relative_path}",
                    checksum=f"sha256:{checksum}",
                    size_bytes=stat.st_size,
                    mtime_ns=stat.st_mtime_ns,
                    artifact_type=_artifact_type(suffix, mime_type),
                    artifact_role=_artifact_role(source.extractor_profile),
                    mime_type=mime_type,
                    language=LANGUAGE_BY_SUFFIX.get(suffix),
                )
            )

        root_identifier = _stable_root_identifier(root)
        version_hash = _snapshot_hash(
            source=source,
            root_identifier=root_identifier,
            artifacts=tuple(artifacts),
        )
        return SourceSnapshot(
            source=source,
            root_identifier=root_identifier,
            source_version_hash=version_hash,
            version_label=f"snapshot:{version_hash[:16]}",
            checksum=f"sha256:{version_hash}",
            artifacts=tuple(artifacts),
        )

    def _resolve_local_root(self, source: SourceConfig) -> Path:
        if source.local_path is None:
            raise LocalDirectoryPathError("local_directory sources require local_path")
        _validate_explicit_relative_path(source.local_path)
        root = (REPOSITORY_ROOT / source.local_path).resolve()
        allowed_roots = [FIXTURE_ALLOWLIST_ROOT.resolve(), *_operator_allowlist_roots()]
        if not any(
            _is_relative_to(root, allowed_root) for allowed_root in allowed_roots
        ):
            raise LocalDirectoryPathError(
                "local_directory path is outside configured allowlist"
            )
        return root


def _validate_explicit_relative_path(value: str) -> None:
    path = Path(value)
    if value.strip() != value or value == "":
        raise LocalDirectoryPathError("local_directory path must be explicit")
    if value.startswith("~") or path.is_absolute():
        raise LocalDirectoryPathError(
            "local_directory path must be relative and must not use home expansion"
        )
    if any(part in {"", ".", ".."} for part in PurePosixPath(value).parts):
        raise LocalDirectoryPathError(
            "local_directory path must be normalized without traversal"
        )


def _operator_allowlist_roots() -> list[Path]:
    raw_value = os.environ.get(ALLOWLIST_ENV_VAR, "")
    roots = []
    for raw_path in raw_value.split(os.pathsep):
        if raw_path:
            roots.append(Path(raw_path).expanduser().resolve())
    return roots


def _relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_hash(
    *,
    source: SourceConfig,
    root_identifier: str,
    artifacts: tuple[ArtifactCandidate, ...],
) -> str:
    payload = {
        "source_id": source.source_id,
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


def _stable_root_identifier(root: Path) -> str:
    if _is_relative_to(root, REPOSITORY_ROOT):
        return root.relative_to(REPOSITORY_ROOT).as_posix()
    return f"allowlisted:{hashlib.sha256(str(root).encode('utf-8')).hexdigest()}"


def _artifact_type(suffix: str, mime_type: str | None) -> str:
    if suffix in {".md", ".markdown", ".txt"}:
        return "document"
    if suffix in {".json", ".yaml", ".yml", ".toml"}:
        return "structured_data"
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


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
