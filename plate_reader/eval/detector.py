"""Detector evaluation with Ultralytics' validator, on a detection set in the data layout.

``plate eval-detector --data synthetic/scenes/detector.yaml`` runs ``YOLO.val`` on the
set's validation split and writes precision, recall, mAP@50 and mAP@50-95 with the set's
provenance and how many photos and plates were measured. On a synthetic scene set
(``plate synth scenes``) the numbers say how the detector does on procedural street
scenes, which is a synthetic result, not real-world accuracy; once real photos exist under
``data/detector`` the same command measures them. Ultralytics reports one pass over the
split without an interval, so none is claimed.

Images load in the main process by default (``workers=0``): spawned loader workers on
Windows die when memory is short, and a validation pass is small.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Final

import yaml

from ..docs_render import SYNTHETIC_LABEL
from ..settings import PROJECT_ROOT

SCHEMA: Final = "detectionx5.eval_detector/1"
IMAGE_SUFFIXES: Final = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".webp"})
PROVENANCE_KEYS: Final = ("kind", "seed", "n", "val_fraction", "generator_version", "digest")


def display_path(path: Path) -> str:
    """``path`` relative to the project root when it lies inside it, else its name."""
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.name


def split_images(data: Path, split: str) -> int | None:
    """Photos in one split of a ``detector.yaml``: a folder of images or a list file.

    Paths resolve as in the data layout and in ``plate synth scenes``: against ``path``
    when the file sets it, else against the folder that holds the file. A ``.txt`` entry
    lists one image per line, as Ultralytics accepts (a set that leaves a photo out of the
    detector's measurement, say because its only box is degenerate, names the others).
    """
    data = data.resolve()
    config = yaml.safe_load(data.read_text(encoding="utf-8")) or {}
    entry = config.get(split)
    if not isinstance(entry, str):
        return None
    root = Path(config["path"]) if isinstance(config.get("path"), str) else data.parent
    if not root.is_absolute():
        root = data.parent / root
    target = root / entry
    if target.is_file() and target.suffix == ".txt":
        lines = target.read_text(encoding="utf-8").splitlines()
        return sum(1 for line in lines if Path(line.strip()).suffix.lower() in IMAGE_SUFFIXES)
    if not target.is_dir():
        return None
    return sum(1 for p in target.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES)


def evaluate_detector(
    data: Path,
    weights: Path,
    *,
    imgsz: int = 640,
    batch: int = 16,
    workers: int = 0,
    split: str = "val",
    device: str | None = None,
    project: Path | None = None,
    synthetic: bool = True,
    note: str | None = None,
) -> dict[str, Any]:
    """One Ultralytics validation pass of ``weights`` on ``split`` of ``data``.

    ``note`` says in words what the set is (and, for real photos, anything that limits what
    the numbers mean); it is kept in the results and rendered beside them.
    """
    ultralytics = importlib.import_module("ultralytics")
    model = ultralytics.YOLO(str(weights))
    metrics = model.val(
        data=str(data.resolve()),
        imgsz=imgsz,
        batch=batch,
        workers=workers,
        split=split,
        device=device,
        plots=False,
        verbose=False,
        project=str(project.resolve()) if project is not None else None,
        name="val",
        exist_ok=True,
    )
    box = metrics.box
    manifest = data.parent / "manifest.json"
    provenance: dict[str, Any] = {}
    if manifest.exists():
        provenance = json.loads(manifest.read_text(encoding="utf-8"))
    plates = metrics.nt_per_class
    with_plates = metrics.nt_per_image
    described = {"note": note.strip()} if note else {}
    return {
        "schema": SCHEMA,
        "label": SYNTHETIC_LABEL if synthetic else "measured on the supplied set",
        "weights": weights.name,
        "data": display_path(data),
        "split": split,
        "imgsz": imgsz,
        "device": device or "auto",  # "auto": Ultralytics picks the first GPU, else the CPU
        "set": {key: provenance[key] for key in PROVENANCE_KEYS if key in provenance},
        **described,
        "counts": {
            "images": split_images(data, split),
            "plates": int(plates.sum()) if plates is not None else None,
            "images_with_plates": int(with_plates.sum()) if with_plates is not None else None,
        },
        "metrics": {
            "precision": round(float(box.mp), 6),
            "recall": round(float(box.mr), 6),
            "map50": round(float(box.map50), 6),
            "map50_95": round(float(box.map), 6),
        },
        "interval": "none: one validation pass, as Ultralytics reports it",
    }


__all__ = ["SCHEMA", "display_path", "evaluate_detector", "split_images"]
