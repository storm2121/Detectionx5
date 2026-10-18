"""``plate export``: ONNX export of the CRNN and the detector, and parity fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

HELP = "Export models to ONNX."

app = typer.Typer(no_args_is_help=True)


@app.command("onnx")
def onnx(
    weights: Annotated[
        Path | None, typer.Option(help="CRNN weights (default models/crnn.pt)")
    ] = None,
    out: Annotated[Path | None, typer.Option(help="ONNX path (default models/crnn.onnx)")] = None,
) -> None:
    """Export the CRNN (opset 17, dynamic batch); keeps calibration in the metadata."""
    from ..settings import PROJECT_ROOT
    from ..training.export_onnx import export_onnx, write_metadata
    from ..training.train_crnn import load_weights

    source = weights or PROJECT_ROOT / "models" / "crnn.pt"
    target = out or PROJECT_ROOT / "models" / "crnn.onnx"
    export_onnx(load_weights(source), target)
    meta = write_metadata(target)
    typer.echo(f"exported {target} (version {meta.version}, {target.stat().st_size} bytes)")


@app.command("fixtures")
def fixtures(
    onnx_path: Annotated[
        Path | None, typer.Option("--onnx", help="default models/crnn.onnx")
    ] = None,
) -> None:
    """Write parity fixtures (PNG crops and the Python pipeline's outputs on them)."""
    from ..crnn.parity import write_fixtures
    from ..crnn.runtime import CRNNRuntime
    from ..settings import PROJECT_ROOT

    runtime = CRNNRuntime(onnx_path or PROJECT_ROOT / "models" / "crnn.onnx")
    payload = write_fixtures(
        runtime,
        PROJECT_ROOT / "tests" / "fixtures" / "parity",
        PROJECT_ROOT / "results" / "parity_fixtures.json",
        PROJECT_ROOT,
    )
    typer.echo(
        f"wrote {len(payload['fixtures'])} parity fixtures for model {payload['model_version']}"
    )


@app.command("detector")
def detector(
    weights: Annotated[Path | None, typer.Option(help="default models/best.pt")] = None,
    out: Annotated[Path | None, typer.Option(help="default models/detector.onnx")] = None,
    imgsz: Annotated[int, typer.Option(min=64)] = 640,
) -> None:
    """Export the YOLOv10 detector to ONNX (opset 17, the NMS-free one-to-one head)."""
    from ..settings import PROJECT_ROOT
    from ..training.export_detector import export_detector

    target = export_detector(
        weights or PROJECT_ROOT / "models" / "best.pt",
        out or PROJECT_ROOT / "models" / "detector.onnx",
        imgsz=imgsz,
    )
    typer.echo(f"exported {target} ({target.stat().st_size} bytes)")


__all__ = ["HELP", "app"]
