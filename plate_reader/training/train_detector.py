"""Fine-tune the plate detector with Ultralytics.

A thin wrapper: Ultralytics owns the training loop; this module fixes the configuration
the shipped ``models/best.pt`` was trained with (YOLOv10n, one class, 100 epochs, image
size 640, batch 16) and copies the run's ``results.csv`` next to the other results so the
docs can render from it. Without real data it can run on a synthetic scene set written by
``plate synth scenes`` (its ``detector.yaml``), which is what the smoke test does.
"""

from __future__ import annotations

import importlib
import shutil
from pathlib import Path
from typing import Any


def train_detector(
    data: Path,
    *,
    epochs: int = 100,
    imgsz: int = 640,
    batch: int = 16,
    workers: int = 8,
    weights: str = "yolov10n.pt",
    project: Path = Path("runs/detector"),
    device: str | None = None,
    amp: bool = True,
    results_dir: Path | None = None,
) -> dict[str, Any]:
    ultralytics = importlib.import_module("ultralytics")
    model = ultralytics.YOLO(weights)
    run = model.train(
        data=str(data.resolve()),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        workers=workers,
        project=str(project.resolve()),
        name="train",
        exist_ok=True,
        device=device,
        amp=amp,
        verbose=False,
        plots=False,
    )
    save_dir = (
        Path(run.save_dir) if run is not None and hasattr(run, "save_dir") else project / "train"
    )
    summary: dict[str, Any] = {
        "run": save_dir.as_posix(),
        "weights": (save_dir / "weights" / "best.pt").as_posix(),
    }
    csv_path = save_dir / "results.csv"
    if results_dir is not None and csv_path.exists():
        results_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(csv_path, results_dir / "detector_training.csv")
        summary["results_csv"] = (results_dir / "detector_training.csv").as_posix()
    return summary


__all__ = ["train_detector"]
