"""Read-only command line interface for idp-brain."""

import typer

from idp_brain import __version__

app = typer.Typer(add_completion=False, help="idp-brain command-line interface.")


@app.callback()
def main() -> None:
    """idp-brain command-line interface."""


@app.command()
def version() -> None:
    """Print the idp-brain package version."""
    typer.echo(__version__)
