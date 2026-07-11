"""Read-only command line interface for idp-brain."""

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from idp_brain import __version__
from idp_brain.config import ConfigError, format_config_error
from idp_brain.db import check_schema, is_local_reset_database_url
from idp_brain.ingestion import IngestionRunResult, run_ingestion
from idp_brain.ingestion.pipeline import IngestionStageNotImplementedError
from idp_brain.ingestion.runs import sanitize_diagnostic_text
from idp_brain.ingestion.source_catalog import SourceCatalogEntry, load_source_catalog
from idp_brain.ingestion.status import IngestionStatus, ingestion_status
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
        list[str] | None,
        typer.Option(
            "--source-id", "--source", help="Repeatable configured source ID filter."
        ),
    ] = None,
    version: Annotated[str | None, typer.Option("--version")] = None,
    profile: Annotated[str | None, typer.Option("--profile")] = None,
    config_dir: Annotated[Path, typer.Option("--config-dir")] = Path("config"),
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            exists=False,
            dir_okay=False,
            help="Path to sources.yaml.",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Record a run without fetching source content.",
        ),
    ] = False,
    operator_label: Annotated[
        str | None,
        typer.Option("--operator", help="Optional local caller label for the run."),
    ] = None,
    output_format: Annotated[
        IngestRunFormat,
        typer.Option("--format", help="Output format."),
    ] = IngestRunFormat.table,
    validation_only: Annotated[
        bool,
        typer.Option("--validation-only/--promote"),
    ] = True,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Record an ingestion run lifecycle for configured sources."""

    if not validation_only:
        typer.echo(
            "Promotion is unavailable until explicit promotion rules are implemented.",
            err=True,
        )
        raise typer.Exit(code=1)
    config_path = config or config_dir / "sources.yaml"

    try:
        results = run_ingestion(
            config_path=config_path,
            source_id=None,
            source_ids=tuple(source_id or ()),
            requested_version=_safe_override(version, "version"),
            profile_override=_safe_override(profile, "profile"),
            dry_run=dry_run,
            operator_label=operator_label,
        )
    except ConfigError as exc:
        typer.echo(format_config_error(exc), err=True)
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        typer.echo(sanitize_diagnostic_text(str(exc)), err=True)
        raise typer.Exit(code=1) from None
    except IngestionStageNotImplementedError as exc:
        typer.echo(sanitize_diagnostic_text(str(exc)), err=True)
        raise typer.Exit(code=1) from None
    except Exception:
        typer.echo("Ingestion failed; inspect sanitized run status.", err=True)
        raise typer.Exit(code=1) from None

    if json_output or output_format == IngestRunFormat.json:
        payload = [_safe_mapping(result.to_dict()) for result in results]
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    _render_table(_ingestion_table(results))


@ingest_app.command("status")
def ingest_status(
    run_id: Annotated[UUID | None, typer.Option("--run-id")] = None,
    source_id: Annotated[str | None, typer.Option("--source-id")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 10,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Inspect sanitized recent ingestion run metadata."""

    try:
        rows = ingestion_status(
            run_id=str(run_id) if run_id else None,
            source_id=_safe_override(source_id, "source ID"),
            limit=limit,
        )
    except ValueError as exc:
        typer.echo(sanitize_diagnostic_text(str(exc)), err=True)
        raise typer.Exit(code=1) from None
    except Exception:
        typer.echo("Unable to read ingestion status.", err=True)
        raise typer.Exit(code=1) from None
    if json_output:
        typer.echo(
            json.dumps([_safe_mapping(row.to_dict()) for row in rows], sort_keys=True)
        )
    else:
        _render_table(_status_table(rows))


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
    console = Console(record=True, force_terminal=False, width=240)
    console.print(_ingestion_table(entries))
    return console.export_text().rstrip()


def _ingestion_table(entries: list[IngestionRunResult]) -> Table:
    headers = [
        "run_id",
        "source_id",
        "version/ref",
        "status",
        "started",
        "finished",
        "changed_chunks",
        "failed_chunks",
        "redacted_chunks",
        "inactive_index_version",
        "validation_only",
    ]
    rows = [
        [
            _safe_cli(str(entry.run_id)),
            _safe_cli(str(entry.source_id)),
            _safe_cli(entry.requested_ref or "-"),
            _safe_cli(entry.status),
            _safe_cli(entry.started_at or "-"),
            _safe_cli(entry.finished_at or "-"),
            str(entry.stats.get("changed_chunks", 0)),
            str(entry.stats.get("failed_artifacts", 0)),
            str(entry.stats.get("redacted_candidates", 0)),
            _safe_cli(entry.inactive_index_version or "-"),
            "true" if entry.validation_only else "false",
        ]
        for entry in entries
    ]
    return _table(headers, rows)


def _status_table(entries: list[IngestionStatus]) -> Table:
    headers = [
        "run_id",
        "source_id",
        "version/ref",
        "status",
        "started",
        "finished",
        "changed_chunks",
        "failed_chunks",
        "redacted_chunks",
        "inactive_index_version",
        "validation_only",
    ]
    rows = [
        [
            row.run_id,
            row.source_id,
            row.version_ref or "-",
            row.status,
            row.started_at,
            row.finished_at or "-",
            str(row.changed_chunk_count),
            str(row.failed_chunk_count),
            str(row.redacted_chunk_count),
            row.inactive_index_version or "-",
            "true" if row.validation_only else "false",
        ]
        for row in entries
    ]
    return _table(headers, rows)


def _table(headers: list[str], rows: list[list[str]]) -> Table:
    table = Table(show_header=True)
    for header in headers:
        table.add_column(header)
    for row in rows:
        table.add_row(*row)
    return table


def _render_table(table: Table) -> None:
    Console(width=240).print(table)


def _safe_override(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    cleaned = sanitize_diagnostic_text(value)
    if cleaned != value or not value.strip() or len(value) > 255:
        raise typer.BadParameter(f"invalid {label}")
    return value


def _safe_mapping(value: dict[str, object]) -> dict[str, object]:
    return {
        key: sanitize_diagnostic_text(item) if isinstance(item, str) else item
        for key, item in value.items()
    }


def _safe_cli(value: str) -> str:
    return sanitize_diagnostic_text(value)
