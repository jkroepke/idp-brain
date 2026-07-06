from typer.testing import CliRunner

from idp_brain import __version__
from idp_brain.cli import app

runner = CliRunner()


def test_help_renders() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "version" in result.output


def test_version_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.output.strip() == __version__
