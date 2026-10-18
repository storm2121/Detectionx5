"""``plate eval``: evaluate recognisers and fusion on a set, write results JSON and HTML."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

HELP = "Evaluate recognisers (and multi-view fusion) with bootstrap intervals."


class SetName(StrEnum):
    synthetic = "synthetic"
    pseudo_real = "pseudo_real"
    data = "data"
    views = "views"


class Device(StrEnum):
    auto = "auto"
    cpu = "cpu"
    cuda = "cuda"


def command(
    set_name: Annotated[
        SetName, typer.Option("--set", help="which set to evaluate")
    ] = SetName.synthetic,
    n: Annotated[int, typer.Option(min=1, help="images for synthetic and pseudo-real sets")] = 300,
    views: Annotated[
        int, typer.Option(min=0, help="multi-view sets to fuse (0 skips fusion)")
    ] = 100,
    k: Annotated[int, typer.Option(min=1, max=10, help="largest number of views per set")] = 5,
    recognizer: Annotated[
        list[str] | None, typer.Option("--recognizer", "-r", help="recogniser(s) to evaluate")
    ] = None,
    resamples: Annotated[int, typer.Option(min=100, help="bootstrap resamples")] = 1000,
    confidence: Annotated[float, typer.Option(min=0.5, max=0.999)] = 0.95,
    seed: Annotated[int, typer.Option(help="bootstrap seed")] = 0,
    out: Annotated[
        Path | None, typer.Option(help="results folder (default PLATE_RESULTS_DIR)")
    ] = None,
    data_dir: Annotated[Path | None, typer.Option(help="data folder for --set data")] = None,
    crops: Annotated[
        Path | None, typer.Option(help="a labels.csv crop folder to evaluate instead")
    ] = None,
    device: Annotated[
        Device, typer.Option(help="device for torch-based recognisers")
    ] = Device.auto,
    quiet: Annotated[bool, typer.Option(help="no progress output")] = False,
    cache: Annotated[
        bool, typer.Option(help="reuse cached reads of slow recognisers (.cache/reads)")
    ] = True,
) -> None:
    from ..eval import harness, recognizers, report, sets
    from ..eval.cache import ReadCache
    from ..settings import PROJECT_ROOT, get_settings

    settings = get_settings()
    names = recognizer or ["easyocr"]
    use_gpu = device == Device.cuda or (device == Device.auto and recognizers.cuda_available())
    built = [recognizers.build(name, use_gpu=use_gpu) for name in names]
    ks = tuple(x for x in harness.DEFAULT_KS if x <= k) or (k,)

    view_set = None
    if crops is not None:
        eval_set = sets.crops_folder_set(crops / "labels.csv" if crops.is_dir() else crops)
        result_name = f"eval_{eval_set.name}"
    elif set_name == SetName.synthetic:
        eval_set = sets.synthetic_set(n)
        view_set = sets.view_sets(views, max(ks)) if views else None
        result_name = "eval_synthetic"
    elif set_name == SetName.pseudo_real:
        eval_set = sets.pseudo_real_set(n)
        result_name = "eval_pseudo_real"
    elif set_name == SetName.data:
        eval_set = sets.data_set(data_dir or settings.data_dir)
        result_name = "eval_data" if eval_set.kind == "data" else f"eval_data_{eval_set.kind}"
        if not eval_set.items:
            typer.echo("no labelled photos under data/eval (the placeholder is empty)", err=True)
            raise typer.Exit(1)
    else:
        if views == 0:
            raise typer.BadParameter("--set views needs --views > 0")
        eval_set = sets.view_sets(views, max(ks))
        view_set = eval_set
        result_name = "eval_views"

    payload = harness.build_payload(
        eval_set,
        built,
        resamples=resamples,
        confidence=confidence,
        seed=seed,
        views=view_set,
        ks=ks,
        device="cuda" if use_gpu else "cpu",
        quiet=quiet,
        cache=ReadCache(PROJECT_ROOT / ".cache" / "reads") if cache else None,
    )
    folder = out or settings.results_dir
    json_path = harness.write_payload(payload, folder / f"{result_name}.json")
    html_path = report.write_report(payload, folder / f"{result_name}.html")
    typer.echo(f"wrote {json_path} and {html_path}")
    if "label" in payload:
        typer.echo(f"{eval_set.kind} set: {payload['label']}")


__all__ = ["HELP", "command"]
