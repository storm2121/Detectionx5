"""``plate synth``: write deterministic synthetic sets to disk."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

HELP = "Generate deterministic synthetic plates (crops, scenes, views, pseudo-real)."

app = typer.Typer(no_args_is_help=True)

Out = Annotated[Path | None, typer.Option(help="output folder (default synthetic/<kind>)")]
Count = Annotated[int, typer.Option(min=1, help="number of samples (sets, for views)")]
Seed = Annotated[int, typer.Option(help="generator seed; equal seeds give identical bytes")]


def _default(kind: str, out: Path | None) -> Path:
    from ..settings import PROJECT_ROOT

    return out if out is not None else PROJECT_ROOT / "synthetic" / kind


def _report(manifest: object) -> None:
    from ..synthetic import Manifest

    assert isinstance(manifest, Manifest)
    typer.echo(f"wrote {manifest.n} {manifest.kind} to {manifest.path.parent}")
    typer.echo(f"digest {manifest.digest}")
    typer.echo("synthetic data: synthetic results are not real-world accuracy")


@app.command("crops")
def crops(out: Out = None, n: Count = 1000, seed: Seed = 0) -> None:
    """Labelled plate crops in the data/ocr layout."""
    from ..synthetic import write_crops

    _report(write_crops(_default("crops", out), n, seed))


@app.command("pseudo-real")
def pseudo_real(out: Out = None, n: Count = 1000, seed: Seed = 0) -> None:
    """Heavily augmented crops standing in for real photos (labelled pseudo-real)."""
    from ..synthetic import write_crops

    _report(write_crops(_default("pseudo_real", out), n, seed, pseudo_real=True))


@app.command("views")
def views(
    out: Out = None,
    n: Count = 200,
    seed: Seed = 0,
    k: Annotated[int, typer.Option(min=1, max=10, help="views per plate")] = 5,
) -> None:
    """Multi-view sets: k photos of one plate under independent conditions."""
    from ..synthetic import write_views

    _report(write_views(_default("views", out), n, k, seed))


@app.command("scenes")
def scenes(
    out: Out = None,
    n: Count = 200,
    seed: Seed = 0,
    val_fraction: Annotated[float, typer.Option(min=0.0, max=1.0)] = 0.2,
) -> None:
    """Procedural scenes with YOLO boxes (detector layout) and an eval labels.csv."""
    from ..synthetic import write_scenes

    _report(write_scenes(_default("scenes", out), n, seed, val_fraction=val_fraction))


__all__ = ["HELP", "app"]
