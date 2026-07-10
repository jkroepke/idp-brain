"""Validate one idp-brain YAML configuration file."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import yaml

from idp_brain.config.errors import (
    ConfigError,
    ConfigFileNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)
from idp_brain.config.loader import (
    load_access_config,
    load_evaluation_config,
    load_extractors_config,
    load_memory_config,
    load_models_config,
    load_retrieval_config,
    load_security_config,
    load_sources_config,
)
from idp_brain.config.models import ConfigModel

ConfigLoader = Callable[[Path], ConfigModel]

CONFIG_LOADERS_BY_KIND: dict[str, ConfigLoader] = {
    "access": load_access_config,
    "evaluation": load_evaluation_config,
    "extractors": load_extractors_config,
    "memory": load_memory_config,
    "models": load_models_config,
    "retrieval": load_retrieval_config,
    "security": load_security_config,
    "sources": load_sources_config,
}


def validate_config_path(path: Path) -> ConfigModel:
    """Validate one YAML config file by its top-level ``kind`` value."""

    kind = _read_kind(path)
    loader = CONFIG_LOADERS_BY_KIND.get(kind)
    if loader is None:
        known_kinds = ", ".join(sorted(CONFIG_LOADERS_BY_KIND))
        raise ConfigValidationError(
            f"unknown config kind {kind!r}; expected one of: {known_kinds}",
            path=path,
        )
    return loader(path)


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entrypoint for ``python -m idp_brain.config.validate``."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="YAML config file to validate")
    args = parser.parse_args(argv)

    try:
        config = validate_config_path(args.path)
    except ConfigError as exc:
        print(f"config validation failed: {exc}", file=sys.stderr)
        return 1

    print(f"valid {config.kind} config: {args.path}")
    return 0


def _read_kind(path: Path) -> str:
    if not path.is_file():
        raise ConfigFileNotFoundError("required config file is missing", path=path)

    try:
        raw_text = path.read_text(encoding="utf-8")
        loaded = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ConfigParseError(
            f"{path.name} is not valid YAML: {exc}",
            path=path,
        ) from exc
    except OSError as exc:
        raise ConfigParseError(
            f"{path.name} could not be read: {exc}",
            path=path,
        ) from exc

    if not isinstance(loaded, dict):
        raise ConfigParseError(f"{path.name} must contain a YAML mapping", path=path)
    kind = loaded.get("kind")
    if not isinstance(kind, str) or not kind:
        raise ConfigValidationError(
            f"{path.name} must declare a non-empty string kind",
            path=path,
        )
    return kind


if __name__ == "__main__":
    raise SystemExit(main())
