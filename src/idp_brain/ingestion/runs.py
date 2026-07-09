"""Helpers for ingestion run metadata and sanitized diagnostics."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from idp_brain.config.models import SourceConfig

SAFE_ERROR_MESSAGE = "ingestion stage failed"


def hash_config_file(config_path: Path) -> str:
    """Return a stable SHA-256 hash for the sources config file."""

    return hashlib.sha256(config_path.read_bytes()).hexdigest()


def select_requested_ref(source: SourceConfig) -> str | None:
    """Return the deterministic requested ref or version selector for a source."""

    if source.tracked_refs:
        return ",".join(source.tracked_refs)
    return source.version_strategy


def sanitized_failure_diagnostic(
    *,
    error: BaseException,
    stage: str,
    source_id: str,
    artifact_locator: str | None = None,
    retryable: bool = False,
) -> dict[str, Any]:
    """Build structured failure data without raw upstream or secret values."""

    diagnostic: dict[str, Any] = {
        "error_type": type(error).__name__,
        "stage": stage,
        "source_id": source_id,
        "retryable": retryable,
    }
    if hasattr(error, "returncode"):
        diagnostic["exit_code"] = getattr(error, "returncode")
    if hasattr(error, "command"):
        safe_command = _safe_command(getattr(error, "command"))
        if safe_command:
            diagnostic["command"] = safe_command
    if artifact_locator is not None:
        diagnostic["artifact_locator"] = _safe_locator(artifact_locator)
    return diagnostic


def _safe_locator(value: str) -> str:
    """Keep only a bounded, non-secret locator tail for diagnostics."""

    cleaned = sanitize_diagnostic_text(value.replace("\\", "/").split("/")[-1])
    return cleaned[:255]


def sanitize_diagnostic_text(value: str) -> str:
    """Return bounded diagnostic text without secret-like values."""

    cleaned = "".join(char if char.isprintable() else " " for char in value)
    cleaned = re.sub(
        r"(?i)\b(token|secret|password|credential|api[_-]?key)\b"
        r"(?:\s*(?:is|=|:)\s*|\s+)\S+",
        "[redacted]",
        cleaned,
    )
    cleaned = re.sub(
        r"(?i)\b(token|secret|password|credential|api[_-]?key)\b",
        "[redacted]",
        cleaned,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:255] or "[empty]"


def _safe_command(value: object) -> list[str]:
    if not isinstance(value, (tuple, list)):
        return []
    safe_parts: list[str] = []
    for part in value:
        text = str(part)
        if "://" in text or "=" in text:
            safe_parts.append("[redacted]")
        else:
            safe_parts.append(Path(text).name if "/" in text else text)
    return safe_parts[:12]
