import tomllib
from pathlib import Path

from typer.testing import CliRunner

from idp_brain.cli import app
from idp_brain.db import is_local_reset_database_url
from idp_brain.settings import load_settings

runner = CliRunner()


def _mise_tasks() -> dict[str, object]:
    with Path("mise.toml").open("rb") as config_file:
        config = tomllib.load(config_file)

    tasks = config["tasks"]
    assert isinstance(tasks, dict)
    return tasks


def _task_sequence(task: dict[str, object]) -> list[str]:
    run = task["run"]
    assert isinstance(run, list)

    task_names: list[str] = []
    for entry in run:
        assert isinstance(entry, dict)
        task_name = entry["task"]
        assert isinstance(task_name, str)
        task_names.append(task_name)

    return task_names


def test_database_tasks_are_discoverable() -> None:
    tasks = _mise_tasks()

    assert "db:migrate" in tasks
    assert "db:current" in tasks
    assert "db:history" in tasks
    assert "db:check" in tasks
    assert "db:reset" in tasks


def test_database_check_is_part_of_ci() -> None:
    tasks = _mise_tasks()
    ci_task = tasks["ci"]
    assert isinstance(ci_task, dict)

    ci_sequence = _task_sequence(ci_task)
    assert ci_sequence == [
        "up",
        "db:migrate",
        "db:check",
        "test:ingestion:integration",
        "test:integration",
    ]
    assert ci_task["depends_post"] == ["down"]


def test_reset_task_requires_confirmation_and_local_target() -> None:
    tasks = _mise_tasks()
    reset_task = tasks["db:reset"]
    assert isinstance(reset_task, dict)

    assert _task_sequence(reset_task) == [
        "db:reset:assert-local",
        "db:reset:remove",
        "up",
        "db:migrate",
        "db:check",
    ]

    assert_task = tasks["db:reset:assert-local"]
    assert isinstance(assert_task, dict)
    assert assert_task["run"] == "uv run idp-brain db assert-local-reset-target"

    remove_task = tasks["db:reset:remove"]
    assert isinstance(remove_task, dict)
    assert remove_task["run"] == "docker compose down --volumes --remove-orphans"


def test_local_reset_database_url_accepts_only_disposable_default() -> None:
    assert is_local_reset_database_url(load_settings().database_url)
    assert not is_local_reset_database_url(
        "postgresql+psycopg://idp_brain:idp_brain@db.example.com:5432/idp_brain"
    )
    assert not is_local_reset_database_url(
        "postgresql+psycopg://idp_brain:idp_brain@localhost:5432/idp_brain"
    )
    assert not is_local_reset_database_url(
        "postgresql+psycopg://admin:idp_brain@localhost:55432/idp_brain"
    )


def test_reset_target_command_requires_confirmation() -> None:
    result = runner.invoke(app, ["db", "assert-local-reset-target"])

    assert result.exit_code == 1
    assert "IDP_BRAIN_CONFIRM_RESET=1" in result.output


def test_reset_target_command_accepts_confirmed_local_default() -> None:
    result = runner.invoke(
        app,
        ["db", "assert-local-reset-target"],
        env={"IDP_BRAIN_CONFIRM_RESET": "1"},
    )

    assert result.exit_code == 0
    assert "disposable local Docker Compose database" in result.output
