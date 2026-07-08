"""Source catalog configuration helpers."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from idp_brain.config.errors import (
    ConfigError,
    ConfigFileNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)


def format_config_error(error: ConfigError) -> str:
    """Return a CLI-safe configuration diagnostic without raw config values."""

    if isinstance(error, ConfigValidationError):
        cause = error.__cause__
        if isinstance(cause, ValidationError):
            details = []
            for item in cause.errors(include_input=False, include_url=False):
                location = ".".join(str(part) for part in item["loc"])
                details.append(f"{location}: {item['msg']}")
            suffix = "; ".join(details)
            prefix = _path_prefix(error.path)
            return f"{prefix}validation failed: {suffix}"

    if isinstance(error, ConfigFileNotFoundError):
        paths = [*error.paths]
        if error.path is not None:
            paths.insert(0, error.path)
        joined = ", ".join(str(path) for path in paths)
        return f"required config file is missing: {joined}"

    if isinstance(error, ConfigParseError):
        return f"{_path_prefix(error.path)}could not parse YAML configuration"

    return f"{_path_prefix(error.path)}{error.message}"


def _path_prefix(path: Path | None) -> str:
    if path is None:
        return ""
    return f"{path}: "
