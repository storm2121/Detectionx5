"""``plate eval-detector``: mAP@50 and mAP@50-95 through Ultralytics validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

HELP = "Detector precision, recall and mAP through Ultralytics validation."


def command(
    data: Annotated[
        Path, typer.Option(help="a detector.yaml (data/detector.yaml or a plate synth scenes set)")
    ],
    weights: Annotated[Path | None, typer.Option(help="default models/best.pt")] = None,
    imgsz: Annotated[int, typer.Option(min=64)] = 640,
    batch: Annotated[int, typer.Option(min=1)] = 16,
    workers: Annotated[
        int, typer.Option(min=0, help="loader workers (0 loads in the main process)")
    ] = 0,
    split: Annotated[str, typer.Option(help="the split of detector.yaml to validate")] = "val",
    device: Annotated[
        str | None, typer.Option(help="cpu, 0, ... (default: Ultralytics' choice)")
    ] = None,
    out: Annotated[
        Path | None, typer.Option(help="results file (default by the set's kind)")
    ] = None,
    note: Annotated[
        str | None,
        typer.Option(help="what the set is, in words; kept in the results and shown beside them"),
    ] = None,
) -> None:
    """Validate the detector on a labelled set and write its metrics with the set's provenance."""
    from ..eval.detector import evaluate_detector
    from ..settings import PROJECT_ROOT

    if not data.exists():
        raise typer.BadParameter(f"{data} does not exist")
    manifest = data.parent / "manifest.json"
    synthetic = (
        manifest.exists()
        and json.loads(manifest.read_text(encoding="utf-8")).get("generator")
        == "detectionx5.synthetic"
    )
    payload = evaluate_detector(
        data,
        weights or PROJECT_ROOT / "models" / "best.pt",
        imgsz=imgsz,
        batch=batch,
        workers=workers,
        split=split,
        device=device,
        project=PROJECT_ROOT / ".cache" / "detector-val",
        synthetic=synthetic,
        note=note,
    )
    name = "eval_detector_synthetic.json" if synthetic else "eval_detector_data.json"
    target = out or PROJECT_ROOT / "results" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    metrics = payload["metrics"]
    typer.echo(
        f"wrote {target}: mAP@50 {metrics['map50']:.3f}, mAP@50-95 {metrics['map50_95']:.3f}"
        + (
            " (synthetic scenes; synthetic results are not real-world accuracy)"
            if synthetic
            else ""
        )
    )


__all__ = ["HELP", "command"]
