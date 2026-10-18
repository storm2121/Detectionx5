"""``plate docs``: render governed numbers from results and check for drift."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ..settings import PROJECT_ROOT

HELP = "Render documentation numbers from results; fail on drift."

app = typer.Typer(no_args_is_help=True)

Files = Annotated[
    list[str] | None, typer.Option("--file", help="governed file(s), relative to the root")
]
Root = Annotated[Path, typer.Option(help="repository root")]


@app.command("render")
def render(root: Root = PROJECT_ROOT, file: Files = None) -> None:
    """Rewrite every render block from docs/training_results.csv and results/*.json."""
    from ..docs_render import render_files

    problems = render_files(root, file)
    for problem in problems:
        typer.echo(str(problem), err=True)
    raise typer.Exit(1 if problems else 0)


@app.command("check")
def check(root: Root = PROJECT_ROOT, file: Files = None) -> None:
    """Fail on drift, on hand-typed metric-like numbers and on missing honesty statements."""
    from ..docs_render import check_files

    problems = check_files(root, file)
    for problem in problems:
        typer.echo(str(problem), err=True)
    if not problems:
        typer.echo("docs are in sync with their sources")
    raise typer.Exit(1 if problems else 0)


__all__ = ["HELP", "app"]
