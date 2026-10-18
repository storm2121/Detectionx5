"""``plate registry``: promote a model version and list the registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

HELP = "The model registry (models/registry.json)."

app = typer.Typer(no_args_is_help=True)


@app.command("promote")
def promote(
    version: Annotated[str, typer.Argument(help="first 12 hex digits of the model file's SHA-256")],
    models_dir: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Record a model version with its metrics and data fingerprint, and make it active."""
    from ..settings import PROJECT_ROOT, get_settings
    from ..training.registry import promote as do_promote

    settings = get_settings()
    try:
        entry = do_promote(
            version, models_dir or PROJECT_ROOT / "models", settings.results_dir, settings.data_dir
        )
    except KeyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(entry, ensure_ascii=False, indent=2))


@app.command("list")
def listing(models_dir: Annotated[Path | None, typer.Option()] = None) -> None:
    """Print the registry."""
    from ..settings import PROJECT_ROOT
    from ..training.registry import listing as do_list

    path = (models_dir or PROJECT_ROOT / "models") / "registry.json"
    typer.echo(json.dumps(do_list(path), ensure_ascii=False, indent=2))


__all__ = ["HELP", "app"]
