"""``plate data``: the real-data placeholder."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from ..settings import get_settings

HELP = "The real-data placeholder: layout and validation."

app = typer.Typer(no_args_is_help=True)


@app.command("validate")
def validate(
    root: Annotated[Path | None, typer.Option(help="data folder (default PLATE_DATA_DIR)")] = None,
    json_: Annotated[bool, typer.Option("--json", help="print the report as JSON")] = False,
    strict: Annotated[bool, typer.Option(help="fail on warnings too")] = False,
) -> None:
    """Check layout, images and labels; an empty placeholder is valid."""
    from ..data import validate_data

    report = validate_data(root or get_settings().data_dir)
    if json_:
        typer.echo(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        if report.is_empty and not report.issues:
            typer.echo(f"{report.root}: empty placeholder (no real data yet); layout is valid.")
        for issue in report.issues:
            typer.echo(str(issue), err=issue.severity == "error")
        counts = ", ".join(f"{k}={v}" for k, v in sorted(report.counts.items()) if v)
        if counts:
            typer.echo(f"counts: {counts}")
        typer.echo(f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    raise typer.Exit(0 if report.ok(strict=strict) else 1)


@app.command("init")
def init(
    root: Annotated[Path | None, typer.Option(help="data folder (default PLATE_DATA_DIR)")] = None,
) -> None:
    """Create the empty folder skeleton (idempotent)."""
    from ..data import DataLayout

    layout = DataLayout((root or get_settings().data_dir).resolve())
    for directory in layout.directories():
        directory.mkdir(parents=True, exist_ok=True)
    typer.echo(f"layout ready under {layout.root}")


__all__ = ["HELP", "app"]
