"""Evaluation sets: synthetic, pseudo-real, multi-view, and the real-data placeholder.

The set kind travels with every item so a result can never be mislabelled: synthetic and
pseudo-real sets come from the generator; ``data`` reads ``data/eval/labels.csv``, but a
folder that carries a generator manifest (a synthetic scene set used to exercise the real
data path) keeps its synthetic kind.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import cv2

from ..detector import pad_box
from ..imaging import Image, as_u8
from ..normalize import parse_plate
from ..settings import PROJECT_ROOT
from ..synthetic.generate import GENERATOR_VERSION, make_crop, make_pseudo_real, make_views
from ..synthetic.splits import SPLIT_SEEDS

SetKind = Literal["synthetic", "pseudo_real", "data"]


@dataclass(frozen=True)
class EvalItem:
    key: str
    image: Image  # a plate crop (BGR)
    truth: str  # canonical tokens
    group: int = 0  # multi-view set id
    view: int = 0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvalSet:
    name: str
    kind: SetKind
    items: list[EvalItem]
    info: dict[str, Any]


def synthetic_set(n: int, seed: int | None = None) -> EvalSet:
    seed = SPLIT_SEEDS["test"] if seed is None else seed
    items = []
    for i in range(n):
        sample = make_crop(seed, i)
        items.append(EvalItem(f"synthetic/{i:06d}", sample.image, sample.tokens, meta=sample.meta))
    info = {
        "seed": seed,
        "generator_version": GENERATOR_VERSION,
        "source": "plate_reader.synthetic",
    }
    return EvalSet("synthetic", "synthetic", items, info)


def pseudo_real_set(n: int, seed: int | None = None) -> EvalSet:
    seed = SPLIT_SEEDS["pseudo_real"] if seed is None else seed
    items = []
    for i in range(n):
        sample = make_pseudo_real(seed, i)
        items.append(
            EvalItem(f"pseudo_real/{i:06d}", sample.image, sample.tokens, meta=sample.meta)
        )
    info = {
        "seed": seed,
        "generator_version": GENERATOR_VERSION,
        "source": "plate_reader.synthetic (pseudo-real preset)",
    }
    return EvalSet("pseudo_real", "pseudo_real", items, info)


def view_sets(n_sets: int, k: int, seed: int | None = None) -> EvalSet:
    seed = SPLIT_SEEDS["views"] if seed is None else seed
    items = []
    for group in range(n_sets):
        for sample in make_views(seed, group, k):
            view = int(sample.meta["view"])
            items.append(
                EvalItem(
                    f"views/{group:05d}_{view}",
                    sample.image,
                    sample.tokens,
                    group,
                    view,
                    sample.meta,
                )
            )
    info = {"seed": seed, "generator_version": GENERATOR_VERSION, "k": k, "n_sets": n_sets}
    return EvalSet("views", "synthetic", items, info)


def repository_path(path: Path) -> str:
    """``path`` relative to the repository, so a results file records no machine's layout.

    A folder outside the repository keeps only its last two parts behind a marker.
    """
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return "<outside the repository>/" + "/".join(resolved.parts[-2:])


def _folder_kind(root: Path) -> SetKind:
    manifest = root / "manifest.json"
    if manifest.exists():
        kind = json.loads(manifest.read_text(encoding="utf-8")).get("set_kind", "synthetic")
        return "pseudo_real" if kind == "pseudo_real" else "synthetic"
    return "data"


def crops_folder_set(labels_csv: Path, name: str | None = None) -> EvalSet:
    """A ``crop_path,plate_text,format`` folder: ``data/ocr/<split>`` or a synthetic crop set."""
    items = []
    with labels_csv.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            plate = parse_plate(row["plate_text"])
            image = cv2.imread(str(labels_csv.parent / row["crop_path"]), cv2.IMREAD_COLOR)
            if plate is None or image is None:
                raise ValueError(f"{labels_csv}: unreadable row {row}; run plate data validate")
            items.append(EvalItem(row["crop_path"], as_u8(image), plate.tokens))
    kind = _folder_kind(labels_csv.parent)
    info = {"source": repository_path(labels_csv)}
    return EvalSet(name or labels_csv.parent.name, kind, items, info)


#: The served detections of one photo: each crop box exactly as the service cuts it (the
#: detector's float box padded, clipped and de-duplicated) with the detector's score.
Detect = Callable[[Image], list[tuple[tuple[int, int, int, int], float]]]


def data_set(data_dir: Path, detect: Detect | None = None) -> EvalSet:
    """``data/eval/labels.csv``: crop the labelled box, or the served detection when it is absent.

    A labelled box is tight, so it is padded exactly as the detector pads its own raw boxes.
    A box from ``detect`` is already the served crop and is cut as it is: padding it again,
    or padding a box rounded to whole pixels first, shifts the crop by a pixel, and the
    EasyOCR path's separator search is sensitive to a pixel at these sizes. Either way the
    recogniser sees the crop it would see in production, and the most confident detection
    is the one the service reads.
    """
    labels = data_dir / "eval" / "labels.csv"
    items: list[EvalItem] = []
    skipped = 0
    with labels.open(encoding="utf-8-sig", newline="") as handle:
        for number, row in enumerate(csv.DictReader(handle)):
            plate = parse_plate(row["plate_text"])
            photo = cv2.imread(str(labels.parent / row["image_path"]), cv2.IMREAD_COLOR)
            if plate is None or photo is None:
                raise ValueError(f"{labels}: unreadable row {row}; run plate data validate")
            image = as_u8(photo)
            h, w = image.shape[:2]
            box_fields = [row[k].strip() for k in ("x1", "y1", "x2", "y2")]
            meta: dict[str, Any]
            if all(box_fields):
                x1, y1, x2, y2 = pad_box([float(v) for v in box_fields], w, h)
                meta = {"box": "label"}
            elif detect is not None:
                found = detect(image)
                if not found:
                    skipped += 1
                    continue
                (x1, y1, x2, y2), score = max(found, key=lambda f: f[1])
                meta = {"box": "detector", "detector_confidence": float(score)}
            else:
                skipped += 1
                continue
            crop = image[y1:y2, x1:x2].copy()
            items.append(EvalItem(f"data/{number:06d}", crop, plate.tokens, meta=meta))
    kind = _folder_kind(data_dir)
    info = {"source": repository_path(labels), "skipped_without_box": skipped}
    return EvalSet("data", kind, items, info)


__all__ = [
    "EvalItem",
    "EvalSet",
    "SetKind",
    "crops_folder_set",
    "data_set",
    "pseudo_real_set",
    "repository_path",
    "synthetic_set",
    "view_sets",
]
