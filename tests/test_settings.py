from collections.abc import Iterator
from pathlib import Path

import pytest

from idp_brain.settings import Settings, load_settings

EXPECTED_ENV_KEYS = {
    "IDP_BRAIN_DATABASE_URL",
    "IDP_BRAIN_LOG_LEVEL",
    "IDP_BRAIN_CONFIG_DIR",
    "IDP_BRAIN_CACHE_DIR",
    "IDP_BRAIN_EMBEDDING_PROVIDER",
    "IDP_BRAIN_EXTERNAL_MODEL_CALLS_ENABLED",
}

SECRET_MARKERS = (
    "api_key",
    "apikey",
    "bearer ",
    "ghp_",
    "password=secret",
    "private_key",
    "token=",
)


@pytest.fixture(autouse=True)
def clean_settings_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in EXPECTED_ENV_KEYS | {"IDP_BRAIN_UNKNOWN_SETTING"}:
        monkeypatch.delenv(key, raising=False)
    load_settings.cache_clear()

    yield

    load_settings.cache_clear()


def test_settings_defaults_are_safe() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url == (
        "postgresql+psycopg://idp_brain:idp_brain@localhost:55432/idp_brain"
    )
    assert settings.log_level == "INFO"
    assert settings.config_dir == Path("config")
    assert settings.cache_dir == Path(".idp-brain-cache")
    assert settings.embedding_provider == "mock"
    assert settings.external_model_calls_enabled is False


def test_environment_overrides(monkeypatch) -> None:
    monkeypatch.setenv("IDP_BRAIN_DATABASE_URL", "postgresql://example/db")
    monkeypatch.setenv("IDP_BRAIN_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("IDP_BRAIN_CONFIG_DIR", "custom-config")
    monkeypatch.setenv("IDP_BRAIN_CACHE_DIR", "custom-cache")
    monkeypatch.setenv("IDP_BRAIN_EMBEDDING_PROVIDER", "local-fixture")
    monkeypatch.setenv("IDP_BRAIN_EXTERNAL_MODEL_CALLS_ENABLED", "true")
    monkeypatch.setenv("IDP_BRAIN_UNKNOWN_SETTING", "ignored")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql://example/db"
    assert settings.log_level == "DEBUG"
    assert settings.config_dir == Path("custom-config")
    assert settings.cache_dir == Path("custom-cache")
    assert settings.embedding_provider == "local-fixture"
    assert settings.external_model_calls_enabled is True


def test_unknown_dotenv_keys_are_ignored(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "IDP_BRAIN_LOG_LEVEL=ERROR",
                "IDP_BRAIN_UNKNOWN_SETTING=ignored",
            ]
        )
    )

    settings = Settings(_env_file=env_file)

    assert settings.log_level == "ERROR"


def test_load_settings_returns_cached_settings(monkeypatch) -> None:
    monkeypatch.setenv("IDP_BRAIN_LOG_LEVEL", "WARNING")

    first = load_settings()
    second = load_settings()

    assert first is second
    assert first.log_level == "WARNING"


def test_env_example_covers_settings_and_contains_no_real_secrets() -> None:
    env_example = Path(".env.example").read_text()
    values = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in env_example.splitlines()
        if line and not line.startswith("#")
    }

    assert values["IDP_BRAIN_DATABASE_URL"] == (
        "postgresql+psycopg://idp_brain:idp_brain@localhost:55432/idp_brain"
    )
    assert values["IDP_BRAIN_LOG_LEVEL"] == "INFO"
    assert values["IDP_BRAIN_CONFIG_DIR"] == "config"
    assert values["IDP_BRAIN_CACHE_DIR"] == ".idp-brain-cache"
    assert values["IDP_BRAIN_EMBEDDING_PROVIDER"] == "mock"
    assert values["IDP_BRAIN_EXTERNAL_MODEL_CALLS_ENABLED"] == "false"

    assert EXPECTED_ENV_KEYS <= values.keys()
    lowered = env_example.lower()
    for marker in SECRET_MARKERS:
        assert marker not in lowered
