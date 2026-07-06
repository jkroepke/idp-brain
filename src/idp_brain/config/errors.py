"""Configuration loader error types."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


class ConfigError(Exception):
    """Base class for actionable configuration errors."""

    def __init__(
        self,
        message: str,
        *,
        path: Path | None = None,
        paths: Iterable[Path] = (),
    ) -> None:
        self.message = message
        self.path = path
        self.paths = tuple(paths)
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        path_parts: list[str] = []
        if self.path is not None:
            path_parts.append(str(self.path))
        path_parts.extend(str(path) for path in self.paths)
        if not path_parts:
            return self.message
        joined_paths = ", ".join(path_parts)
        return f"{self.message} ({joined_paths})"


class ConfigFileNotFoundError(ConfigError):
    """Raised when one or more required config files are missing."""


class ConfigParseError(ConfigError):
    """Raised when a YAML file cannot be parsed into a mapping."""


class ConfigValidationError(ConfigError):
    """Raised when a config file fails Pydantic validation."""


class ConfigReferenceError(ConfigError):
    """Raised when cross-file references cannot be resolved."""
