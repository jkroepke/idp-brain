from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from idp_brain.config.errors import (
    ConfigFileNotFoundError,
    ConfigValidationError,
)
from idp_brain.config.validate import main, validate_config_path


def test_validate_config_path_loads_retrieval_config() -> None:
    config = validate_config_path(Path("config/retrieval.yaml"))

    assert config.kind == "retrieval"


def test_validate_module_main_prints_success(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["config/retrieval.yaml"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "valid retrieval config" in captured.out
    assert captured.err == ""


def test_validate_module_main_reports_validation_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = yaml.safe_load(Path("config/retrieval.yaml").read_text(encoding="utf-8"))
    payload["query_profiles"][0]["candidate_counts"]["bm25_top_k"] = 0
    path = tmp_path / "retrieval.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    exit_code = main([str(path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "config validation failed" in captured.err
    assert "bm25_top_k" in captured.err


def test_validate_config_path_rejects_unknown_kind(tmp_path: Path) -> None:
    path = tmp_path / "unknown.yaml"
    path.write_text(
        yaml.safe_dump({"config_version": 1, "kind": "unknown"}),
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError, match="unknown config kind"):
        validate_config_path(path)


def test_validate_config_path_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigFileNotFoundError, match="required config file"):
        validate_config_path(tmp_path / "missing.yaml")
