"""Read-only command line interface for idp-brain."""

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from idp_brain import __version__
from idp_brain.config import ConfigError, format_config_error
from idp_brain.db import check_schema, is_local_reset_database_url
from idp_brain.ingestion import IngestionRunResult, run_ingestion
from idp_brain.ingestion.pipeline import IngestionStageNotImplementedError
from idp_brain.ingestion.source_catalog import SourceCatalogEntry, load_source_catalog
from idp_brain.settings import load_settings

app = typer.Typer(add_completion=False, help="idp-brain command-line interface.")
db_app = typer.Typer(
    add_completion=False,
    help="Database workflow helpers for local development.",
)
sources_app = typer.Typer(
    add_completion=False,
    help="Read source catalog metadata without fetching source content.",
)
ingest_app = typer.Typer(
    add_completion=False,
    help="Record local ingestion runs.",
)
app.add_typer(db_app, name="db")
app.add_typer(sources_app, name="sources")
app.add_typer(ingest_app, name="ingest")


class SourceListFormat(StrEnum):
    """Supported source catalog output formats."""

    table = "table"
    json = "json"


class IngestRunFormat(StrEnum):
    """Supported ingestion run output formats."""

    table = "table"
    json = "json"


@app.callback()
def main() -> None:
    """idp-brain command-line interface."""


@app.command()
def version() -> None:
    """Print the idp-brain package version."""
    typer.echo(__version__)


@sources_app.command("list")
def sources_list(
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            exists=False,
            dir_okay=False,
            help="Path to sources.yaml.",
        ),
    ] = Path("config/sources.yaml"),
    output_format: Annotated[
        SourceListFormat,
        typer.Option("--format", help="Output format."),
    ] = SourceListFormat.table,
) -> None:
    """List configured source catalog metadata."""

    try:
        entries = load_source_catalog(config)
    except ConfigError as exc:
        typer.echo(format_config_error(exc), err=True)
        raise typer.Exit(code=1) from exc

    if output_format == SourceListFormat.json:
        payload = [entry.to_dict() for entry in entries]
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    typer.echo(_format_sources_table(entries))


@ingest_app.command("run")
def ingest_run(
    source_id: Annotated[
        str | None,
        typer.Option("--source", help="Source ID to ingest; omit for all enabled."),
    ] = None,
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            exists=False,
            dir_okay=False,
            help="Path to sources.yaml.",
        ),
    ] = Path("config/sources.yaml"),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Record a run without fetching source content."),
    ] = False,
    operator_label: Annotated[
        str | None,
        typer.Option("--operator", help="Optional local caller label for the run."),
    ] = None,
    output_format: Annotated[
        IngestRunFormat,
        typer.Option("--format", help="Output format."),
    ] = IngestRunFormat.table,
) -> None:
    """Record an ingestion run lifecycle for configured sources."""

    try:
        results = run_ingestion(
            config_path=config,
            source_id=source_id,
            dry_run=dry_run,
            operator_label=operator_label,
        )
    except ConfigError as exc:
        typer.echo(format_config_error(exc), err=True)
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except IngestionStageNotImplementedError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    if output_format == IngestRunFormat.json:
        payload = [result.to_dict() for result in results]
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    typer.echo(_format_ingestion_runs_table(results))


@db_app.command("check")
def db_check() -> None:
    """Verify required extensions and Phase 2 tables in the configured database."""

    result = check_schema()
    if not result.passed:
        if result.missing_extensions:
            typer.echo(
                "Missing PostgreSQL extensions: "
                + ", ".join(result.missing_extensions),
                err=True,
            )
        if result.missing_tables:
            typer.echo(
                "Missing Phase 2 tables: " + ", ".join(result.missing_tables),
                err=True,
            )
        raise typer.Exit(code=1)

    typer.echo("Database schema check passed.")
    typer.echo("Extensions: " + ", ".join(result.extensions))
    typer.echo(f"Phase 2 tables present: {len(result.tables)}")


@db_app.command("assert-local-reset-target")
def db_assert_local_reset_target(
    confirm: Annotated[
        str | None,
        typer.Option(
            envvar="IDP_BRAIN_CONFIRM_RESET",
            help="Must be set to 1 before resetting the local database.",
        ),
    ] = None,
) -> None:
    """Fail unless reset is explicitly confirmed for the disposable local DB."""

    if confirm != "1":
        typer.echo(
            "Set IDP_BRAIN_CONFIRM_RESET=1 to reset the local database.", err=True
        )
        raise typer.Exit(code=1)

    settings = load_settings()
    if not is_local_reset_database_url(settings.database_url):
        typer.echo(
            "Refusing reset because IDP_BRAIN_DATABASE_URL is not the disposable "
            "local Docker Compose database.",
            err=True,
        )
        raise typer.Exit(code=1)

    typer.echo("Confirmed reset target: disposable local Docker Compose database.")


def _format_sources_table(entries: list[SourceCatalogEntry]) -> str:
    headers = [
        "source_id",
        "type",
        "refs_or_strategy",
        "extractor",
        "priority",
        "visibility",
        "corpus",
        "sensitivity",
        "license",
        "refresh",
        "enabled",
    ]
    rows = [
        [
            entry.source_id,
            entry.source_type,
            ", ".join(entry.tracked_refs)
            if entry.tracked_refs
            else entry.version_strategy,
            entry.extractor_profile,
            str(entry.source_priority),
            entry.visibility_label,
            entry.corpus_eligibility,
            entry.sensitivity_class,
            entry.license_policy,
            entry.refresh_cadence,
            "true" if entry.enabled else "false",
        ]
        for entry in entries
    ]
    widths = [
        max(len(row[index]) for row in [headers, *rows])
        for index in range(len(headers))
    ]
    lines = [
        " | ".join(value.ljust(widths[index]) for index, value in enumerate(headers)),
        "-+-".join("-" * width for width in widths),
    ]
    lines.extend(
        " | ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )
    return "\n".join(lines)


def _format_ingestion_runs_table(entries: list[IngestionRunResult]) -> str:
    headers = ["run_id", "source_id", "status", "dry_run"]
    rows = [
        [
            str(entry.run_id),
            str(entry.source_id),
            str(entry.status),
            "true" if entry.dry_run else "false",
        ]
        for entry in entries
    ]
    widths = [
        max(len(row[index]) for row in [headers, *rows])
        for index in range(len(headers))
    ]
    lines = [
        " | ".join(value.ljust(widths[index]) for index, value in enumerate(headers)),
        "-+-".join("-" * width for width in widths),
    ]
    lines.extend(
        " | ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )
    return "\n".join(lines)
