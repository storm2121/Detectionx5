"""Evaluation sets: synthetic, pseudo-real, multi-view, and the labelled real photos.

The set kind travels with every item so a result can never be mislabelled: synthetic and
pseudo-real sets come from the generator; ``data`` reads ``data/eval/labels.csv``, but a
folder that carries a generator manifest (a synthetic scene set used to exercise the real
data path) keeps its synthetic kind.

``data/eval/labels.csv`` is read two ways: from the labelled boxes (:func:`data_set`, one
item per plate) and end to end with the detector (:func:`data_photos_set`, one item per
photo, the boxes ignored). A ``group`` column makes the bootstrap resample groups, and a
``card.json`` beside the CSV travels into the results as the set's description (ADR 0013).
"""

from __future__ import annotations

import csv
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

import cv2
import numpy as np

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
    #: The bootstrap resamples ``EvalItem.group`` instead of single items.
    grouped: bool = False


#: An item without a crop: the detector found nothing in the photo, so nothing was read.
NO_CROP: Final = np.zeros((0, 0, 3), dtype=np.uint8)


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


def _box_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _labelled_rows(labels: Path) -> list[dict[str, str]]:
    with labels.open(encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _set_info(data_dir: Path, labels: Path, rows: list[dict[str, str]]) -> dict[str, Any]:
    """Provenance shared by both readings of the CSV: source, photos, groups, the card."""
    info: dict[str, Any] = {
        "source": repository_path(labels),
        "photos": len({row["image_path"] for row in rows}),
    }
    if rows and "group" in rows[0]:
        info["groups"] = len({row["group"].strip() for row in rows})
    card = data_dir / "eval" / "card.json"
    if card.exists():
        info["card"] = json.loads(card.read_text(encoding="utf-8"))
    return info


def _group_ids(rows: list[dict[str, str]]) -> dict[str, int] | None:
    """Group label to a small integer, in order of first appearance; None without groups."""
    if not rows or "group" not in rows[0]:
        return None
    ids: dict[str, int] = {}
    for row in rows:
        ids.setdefault(row["group"].strip(), len(ids))
    return ids


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
    rows = _labelled_rows(labels)
    groups = _group_ids(rows)
    items: list[EvalItem] = []
    skipped = 0
    for number, row in enumerate(rows):
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
        group = groups[row["group"].strip()] if groups is not None else 0
        items.append(EvalItem(f"data/{number:06d}", crop, plate.tokens, group=group, meta=meta))
    kind = _folder_kind(data_dir)
    info = {**_set_info(data_dir, labels, rows), "skipped_without_box": skipped}
    return EvalSet("data", kind, items, info, grouped=groups is not None)


def data_photos_set(data_dir: Path, detect: Detect) -> EvalSet:
    """``data/eval/labels.csv`` end to end: each photo once, read as the service reads it.

    The labelled boxes never choose the crop. The service reads a photo's most confident
    detection, so that crop is the photo's read, cut exactly where the service cuts it; a
    photo where the detector finds nothing becomes an item without a crop (:data:`NO_CROP`),
    which every metric scores as a read that returned nothing. The labelled boxes only
    decide which of a photo's plates the read is scored against (the one the detection
    overlaps most, the boxes compared padded as the service pads them) and whether the
    detection lies on a labelled plate at all (``on_plate``: an overlap of at least one half).
    """
    labels = data_dir / "eval" / "labels.csv"
    rows = _labelled_rows(labels)
    groups = _group_ids(rows)
    photos: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        photos.setdefault(row["image_path"], []).append(row)
    items: list[EvalItem] = []
    missed = 0
    for number, (image_path, plates) in enumerate(photos.items()):
        photo = cv2.imread(str(labels.parent / image_path), cv2.IMREAD_COLOR)
        parsed = [parse_plate(row["plate_text"]) for row in plates]
        if photo is None or any(p is None for p in parsed):
            raise ValueError(f"{labels}: unreadable rows for {image_path}; run plate data validate")
        image = as_u8(photo)
        h, w = image.shape[:2]
        found = detect(image)
        chosen = 0
        crop = NO_CROP
        meta: dict[str, Any] = {"box": "none", "on_plate": 0.0}
        if found:
            box, score = max(found, key=lambda f: f[1])
            overlaps = []
            for row in plates:
                fields = [row[k].strip() for k in ("x1", "y1", "x2", "y2")]
                padded = pad_box([float(v) for v in fields], w, h) if all(fields) else None
                overlaps.append(_box_iou(box, padded) if padded is not None else 0.0)
            chosen = max(range(len(plates)), key=lambda i: overlaps[i])
            x1, y1, x2, y2 = box
            crop = image[y1:y2, x1:x2].copy()
            meta = {
                "box": "detector",
                "detector_confidence": float(score),
                "iou": round(overlaps[chosen], 6),
                "on_plate": float(overlaps[chosen] >= 0.5),
            }
        else:
            missed += 1
        plate = parsed[chosen]
        if plate is None:  # pragma: no cover - rejected above
            raise ValueError(image_path)
        group = groups[plates[chosen]["group"].strip()] if groups is not None else number
        items.append(EvalItem(f"photo/{number:06d}", crop, plate.tokens, group=group, meta=meta))
    kind = _folder_kind(data_dir)
    info = {
        **_set_info(data_dir, labels, rows),
        "plates": len(rows),
        "read": "end to end: the most confident detection of each photo, labelled boxes ignored",
        "no_detection": missed,
    }
    return EvalSet("data", kind, items, info, grouped=groups is not None)


__all__ = [
    "NO_CROP",
    "EvalItem",
    "EvalSet",
    "SetKind",
    "crops_folder_set",
    "data_photos_set",
    "data_set",
    "pseudo_real_set",
    "repository_path",
    "synthetic_set",
    "view_sets",
]
