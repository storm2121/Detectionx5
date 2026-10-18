"""``plate train``: the CRNN (synthetic pretraining, optional fine-tune), calibration, detector."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

HELP = "Train the CRNN or the detector, and calibrate the CRNN."

app = typer.Typer(no_args_is_help=True)


def _write_json(payload: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@app.command("crnn")
def crnn(
    epochs: Annotated[int, typer.Option(min=1)] = 24,
    epoch_size: Annotated[int, typer.Option(min=16, help="synthetic crops per epoch")] = 20000,
    batch_size: Annotated[int, typer.Option(min=2)] = 128,
    lr: Annotated[float, typer.Option(min=1e-6)] = 2e-3,
    workers: Annotated[int, typer.Option(min=0, help="DataLoader worker processes")] = 6,
    val_size: Annotated[int, typer.Option(min=8)] = 1000,
    device: Annotated[str, typer.Option(help="auto, cpu or cuda")] = "auto",
    seed: Annotated[int, typer.Option()] = 0,
    data_dir: Annotated[
        Path | None, typer.Option(help="real data root; fine-tunes on ocr/train when present")
    ] = None,
    models_dir: Annotated[Path | None, typer.Option(help="where crnn.pt and crnn.onnx go")] = None,
    results_dir: Annotated[Path | None, typer.Option(help="where the JSON results go")] = None,
    calibrate: Annotated[
        bool, typer.Option(help="fit temperature and conformal thresholds")
    ] = True,
    n_calibration: Annotated[int, typer.Option(min=20)] = 2000,
) -> None:
    """Pretrain on synthetic crops (curriculum), export ONNX, then calibrate."""
    from ..settings import PROJECT_ROOT, get_settings
    from ..training.calibrate_crnn import calibrate as run_calibration
    from ..training.export_onnx import export_onnx, write_metadata
    from ..training.train_crnn import TrainConfig, save_weights, train, training_summary

    settings = get_settings()
    models = models_dir or PROJECT_ROOT / "models"
    results = results_dir or settings.results_dir
    config = TrainConfig(
        epochs=epochs,
        epoch_size=epoch_size,
        batch_size=batch_size,
        lr=lr,
        workers=workers,
        val_size=val_size,
        device=device,
        seed=seed,
        data_dir=data_dir if data_dir is not None else settings.data_dir,
        checkpoint=models / "checkpoints" / "crnn_best.pt",
    )
    result = train(config, log=typer.echo)
    save_weights(result.model, models / "crnn.pt")
    onnx_path = export_onnx(result.model, models / "crnn.onnx")
    from ..crnn.runtime import CRNNMetadata
    from ..synthetic.generate import GENERATOR_VERSION

    meta = write_metadata(
        onnx_path,
        CRNNMetadata(
            version="",
            training={
                "best_epoch": result.best_epoch,
                "best_val_exact_greedy": round(result.best_val, 6),
                "parameters": result.parameters,
                "device": result.device,
                "fine_tuned_on_real_data": result.fine_tuned,
                "generator_version": GENERATOR_VERSION,
            },
            set_kind="synthetic" if not result.fine_tuned else "synthetic+data",
        ),
    )
    summary = training_summary(config, result)
    summary["model_version"] = meta.version
    _write_json(summary, results / "train_crnn.json")
    typer.echo(f"exported {onnx_path} (version {meta.version})")
    if calibrate:
        payload = run_calibration(
            onnx_path, n_calibration, n_calibration, n_calibration, log=typer.echo
        )
        _write_json(payload, results / "calibration_crnn.json")
        typer.echo(f"calibrated: temperature {payload['temperature']['temperature']}")
        from ..training.calibrate_fused import calibrate_fused

        _write_json(calibrate_fused(onnx_path, log=typer.echo), results / "calibration_fused.json")


@app.command("calibrate")
def calibrate(
    onnx: Annotated[
        Path | None, typer.Option(help="exported CRNN (default models/crnn.onnx)")
    ] = None,
    n: Annotated[int, typer.Option(min=20, help="crops per split")] = 2000,
    resamples: Annotated[int, typer.Option(min=100)] = 1000,
    results_dir: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Fit the temperature and conformal thresholds of an exported CRNN."""
    from ..settings import PROJECT_ROOT, get_settings
    from ..training.calibrate_crnn import calibrate as run_calibration

    path = onnx or PROJECT_ROOT / "models" / "crnn.onnx"
    payload = run_calibration(path, n, n, n, resamples=resamples, log=typer.echo)
    _write_json(payload, (results_dir or get_settings().results_dir) / "calibration_crnn.json")
    typer.echo(f"calibrated {path}: temperature {payload['temperature']['temperature']}")


@app.command("calibrate-fused")
def calibrate_fused_command(
    onnx: Annotated[
        Path | None, typer.Option(help="exported CRNN (default models/crnn.onnx)")
    ] = None,
    n_sets: Annotated[int, typer.Option(min=20, help="multi-view calibration sets")] = 1000,
    resamples: Annotated[int, typer.Option(min=100)] = 1000,
    results_dir: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Fit conformal thresholds for fused reads of 1, 3 and 5 views (synthetic sets)."""
    from ..settings import PROJECT_ROOT, get_settings
    from ..training.calibrate_fused import calibrate_fused

    path = onnx or PROJECT_ROOT / "models" / "crnn.onnx"
    payload = calibrate_fused(path, n_sets, resamples=resamples, log=typer.echo)
    _write_json(payload, (results_dir or get_settings().results_dir) / "calibration_fused.json")
    typer.echo(
        f"fused thresholds for {payload['views']} views written to {path.with_suffix('.json')}"
    )


@app.command("detector")
def detector(
    data: Annotated[Path, typer.Option(help="Ultralytics dataset YAML")] = Path(
        "data/detector.yaml"
    ),
    epochs: Annotated[int, typer.Option(min=1)] = 100,
    imgsz: Annotated[int, typer.Option(min=64)] = 640,
    batch: Annotated[int, typer.Option(min=1)] = 16,
    weights: Annotated[str, typer.Option(help="starting weights")] = "yolov10n.pt",
    project: Annotated[Path, typer.Option(help="Ultralytics run folder")] = Path("runs/detector"),
) -> None:
    """Fine-tune the YOLOv10 detector with Ultralytics (needs real data or synthetic scenes)."""
    from ..training.train_detector import train_detector

    summary = train_detector(
        data, epochs=epochs, imgsz=imgsz, batch=batch, weights=weights, project=project
    )
    typer.echo(json.dumps(summary, indent=2))


__all__ = ["HELP", "app"]
