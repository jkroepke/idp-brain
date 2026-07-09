"""Deterministic POSIX path matching helpers for artifact discovery."""

from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath


def normalize_relative_path(path: str) -> str:
    """Normalize a source-relative path and reject traversal."""

    normalized = PurePosixPath(path.replace("\\", "/"))
    if normalized.is_absolute() or any(
        part in {"", ".", ".."} for part in normalized.parts
    ):
        raise ValueError("artifact paths must be normalized relative POSIX paths")
    return normalized.as_posix()


def first_matching_pattern(path: str, patterns: list[str]) -> str | None:
    """Return the first glob pattern matching ``path``."""

    normalized = normalize_relative_path(path)
    for pattern in patterns:
        if matches_pattern(normalized, pattern):
            return pattern
    return None


def matches_includes(path: str, patterns: list[str]) -> bool:
    """Return whether ``path`` is included by the configured glob list."""

    return not patterns or first_matching_pattern(path, patterns) is not None


def matches_pattern(path: str, pattern: str) -> bool:
    """Match a POSIX path against repository-style glob patterns."""

    normalized_pattern = pattern.replace("\\", "/")
    if fnmatch.fnmatchcase(path, normalized_pattern):
        return True
    if normalized_pattern.startswith("**/") and fnmatch.fnmatchcase(
        path, normalized_pattern[3:]
    ):
        return True
    return False
