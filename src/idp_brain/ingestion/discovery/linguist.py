"""Optional GitHub Linguist adapter with deterministic fallback classification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class LinguistClassification:
    """Language and repository-role signals for one artifact path."""

    language: str | None
    generated: bool
    vendored: bool


class LinguistAdapter:
    """Adapter boundary for optional GitHub Linguist integration.

    The MVP runtime does not depend on Ruby or GitHub Linguist. This adapter keeps the
    integration point explicit while returning deterministic local classifications.
    """

    def classify_path(self, path: str) -> LinguistClassification:
        return fallback_classify_path(path)


LANGUAGE_BY_SUFFIX = {
    ".c": "c",
    ".cc": "c++",
    ".cpp": "c++",
    ".css": "css",
    ".go": "go",
    ".html": "html",
    ".htm": "html",
    ".java": "java",
    ".js": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".markdown": "markdown",
    ".mdx": "mdx",
    ".py": "python",
    ".rs": "rust",
    ".sh": "shell",
    ".toml": "toml",
    ".ts": "typescript",
    ".txt": "text",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
}

VENDORED_PARTS = {
    "node_modules",
    "vendor",
    "vendors",
    "third_party",
    "third-party",
    "external",
    "deps",
}

GENERATED_PARTS = {
    "generated",
    "gen",
    "dist",
    "build",
    "coverage",
}

GENERATED_SUFFIXES = {
    ".generated.py",
    ".generated.ts",
    ".generated.js",
    ".pb.go",
    ".pb.py",
    ".pb.cc",
    ".min.js",
    ".min.css",
}


def fallback_classify_path(path: str) -> LinguistClassification:
    """Classify using path, suffix, and common generated/vendor conventions."""

    posix_path = PurePosixPath(path)
    lowered_parts = {part.lower() for part in posix_path.parts}
    lowered_path = posix_path.as_posix().lower()
    suffix = posix_path.suffix.lower()
    generated = bool(lowered_parts & GENERATED_PARTS) or any(
        lowered_path.endswith(generated_suffix)
        for generated_suffix in GENERATED_SUFFIXES
    )
    if re.search(r"(^|[-_.])generated([-_.]|$)", posix_path.name.lower()):
        generated = True
    vendored = bool(lowered_parts & VENDORED_PARTS)
    return LinguistClassification(
        language=LANGUAGE_BY_SUFFIX.get(suffix),
        generated=generated,
        vendored=vendored,
    )
