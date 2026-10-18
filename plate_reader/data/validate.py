"""Validate the real-data folder before anything is trained or measured on it.

The validator is deliberately strict about labels (a plate text the grammar rejects is an
error, not a warning) because one bad label silently corrupts every metric computed from
the set. An empty layout is valid: that is the normal state of the repository.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from PIL import Image as PILImage
from PIL import UnidentifiedImageError

from ..grammar import FORMAT_NAMES
from ..normalize import parse_plate
from .layout import (
    DETECTOR_CLASS_NAMES,
    EVAL_COLUMNS,
    IMAGE_SUFFIXES,
    OCR_COLUMNS,
    SPLITS,
    DataLayout,
)

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Issue:
    severity: Severity
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.severity}: {self.where}: {self.message}"


@dataclass
class ValidationReport:
    root: Path
    issues: list[Issue] = field(default_factory=list)
    counts: Counter[str] = field(default_factory=Counter)

    def error(self, where: Path | str, message: str) -> None:
        self.issues.append(Issue("error", self._rel(where), message))

    def warning(self, where: Path | str, message: str) -> None:
        self.issues.append(Issue("warning", self._rel(where), message))

    def _rel(self, where: Path | str) -> str:
        if isinstance(where, Path):
            try:
                return where.relative_to(self.root).as_posix()
            except ValueError:
                return where.as_posix()
        return where

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def is_empty(self) -> bool:
        return sum(self.counts.values()) == 0

    def ok(self, strict: bool = False) -> bool:
        return not self.errors and not (strict and self.warnings)

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": self.root.as_posix(),
            "empty": self.is_empty,
            "counts": dict(sorted(self.counts.items())),
            "errors": [vars(i) for i in self.errors],
            "warnings": [vars(i) for i in self.warnings],
        }


def _image_size(path: Path) -> tuple[int, int] | None:
    try:
        with PILImage.open(path) as image:
            image.verify()
        with PILImage.open(path) as image:
            return image.size
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _check_plate(report: ValidationReport, where: str, text: str, fmt: str) -> None:
    plate = parse_plate(text)
    if plate is None:
        report.error(where, f"plate_text {text!r} is not a valid plate under the grammar")
        return
    if plate.text != text:
        report.warning(where, f"plate_text {text!r} is not canonical; expected {plate.text!r}")
    if fmt not in FORMAT_NAMES:
        report.error(where, f"format {fmt!r} must be one of {', '.join(FORMAT_NAMES)}")
    elif fmt != plate.format:
        report.error(where, f"format {fmt!r} contradicts the plate text ({plate.format})")


def _read_csv(
    report: ValidationReport, path: Path, columns: tuple[str, ...]
) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        if header != columns:
            report.error(path, f"header must be {','.join(columns)} (found {','.join(header)})")
            return []
        return [dict(row) for row in reader]


def _validate_detector(report: ValidationReport, layout: DataLayout) -> None:
    for split in SPLITS:
        images_dir, labels_dir = layout.detector_images(split), layout.detector_labels(split)
        images = (
            {p.stem: p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES}
            if images_dir.is_dir()
            else {}
        )
        labels = (
            {p.stem: p for p in labels_dir.iterdir() if p.suffix == ".txt"}
            if labels_dir.is_dir()
            else {}
        )
        report.counts[f"detector_{split}_images"] = len(images)
        for stem in sorted(set(labels) - set(images)):
            report.error(labels[stem], "label file without a matching image")
        for stem in sorted(set(images) - set(labels)):
            report.warning(images[stem], "image without a label file (treated as background)")
        for stem in sorted(set(images) & set(labels)):
            if _image_size(images[stem]) is None:
                report.error(images[stem], "image cannot be decoded")
            lines = labels[stem].read_text(encoding="utf-8").splitlines()
            for number, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                parts = line.split()
                where = f"{report._rel(labels[stem])}:{number}"
                if len(parts) != 5:
                    report.error(where, "a YOLO box line has five fields: class cx cy w h")
                    continue
                try:
                    cls = int(parts[0])
                    cx, cy, w, h = (float(v) for v in parts[1:])
                except ValueError:
                    report.error(where, "non-numeric field in YOLO box line")
                    continue
                if cls != 0:
                    report.error(where, f"class {cls} out of range (single class LP is 0)")
                if not all(0.0 <= v <= 1.0 for v in (cx, cy, w, h)) or w <= 0 or h <= 0:
                    report.error(where, "box coordinates must be normalised to (0, 1]")
                report.counts[f"detector_{split}_boxes"] += 1

    has_images = any(report.counts[f"detector_{s}_images"] for s in SPLITS)
    if layout.detector_yaml.exists():
        try:
            config = yaml.safe_load(layout.detector_yaml.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            report.error(layout.detector_yaml, f"invalid YAML: {exc}")
            return
        names = config.get("names")
        values = list(names.values()) if isinstance(names, dict) else list(names or [])
        if tuple(values) != DETECTOR_CLASS_NAMES:
            report.error(layout.detector_yaml, f"names must be {list(DETECTOR_CLASS_NAMES)}")
    elif has_images:
        report.error(layout.detector_yaml, "missing: detector images exist without detector.yaml")


def _validate_ocr(report: ValidationReport, layout: DataLayout) -> None:
    for split in SPLITS:
        path = layout.ocr_labels(split)
        report.counts[f"ocr_{split}_crops"] = 0
        if not path.exists():
            continue
        seen: set[str] = set()
        for number, row in enumerate(_read_csv(report, path, OCR_COLUMNS), start=2):
            where = f"{report._rel(path)}:{number}"
            crop = row["crop_path"]
            if crop in seen:
                report.error(where, f"duplicate crop_path {crop!r}")
            seen.add(crop)
            crop_path = path.parent / crop
            if not crop_path.is_file():
                report.error(where, f"crop {crop!r} does not exist")
            elif _image_size(crop_path) is None:
                report.error(where, f"crop {crop!r} cannot be decoded")
            _check_plate(report, where, row["plate_text"], row["format"])
            report.counts[f"ocr_{split}_crops"] += 1


def _validate_eval(report: ValidationReport, layout: DataLayout) -> None:
    path = layout.eval_labels
    report.counts["eval_images"] = 0
    if not path.exists():
        return
    for number, row in enumerate(_read_csv(report, path, EVAL_COLUMNS), start=2):
        where = f"{report._rel(path)}:{number}"
        image_path = path.parent / row["image_path"]
        size = _image_size(image_path) if image_path.is_file() else None
        if not image_path.is_file():
            report.error(where, f"image {row['image_path']!r} does not exist")
        elif size is None:
            report.error(where, f"image {row['image_path']!r} cannot be decoded")
        _check_plate(report, where, row["plate_text"], row["format"])
        box = [row[k].strip() for k in ("x1", "y1", "x2", "y2")]
        if any(box) and not all(box):
            report.error(where, "a bounding box needs all of x1,y1,x2,y2 or none")
        elif all(box):
            try:
                x1, y1, x2, y2 = (int(v) for v in box)
            except ValueError:
                report.error(where, "bounding box coordinates must be integers in pixels")
            else:
                if not (0 <= x1 < x2 and 0 <= y1 < y2):
                    report.error(where, "bounding box must satisfy 0 <= x1 < x2 and 0 <= y1 < y2")
                elif size is not None and (x2 > size[0] or y2 > size[1]):
                    report.error(where, "bounding box exceeds the image")
        report.counts["eval_images"] += 1


def validate_data(root: Path) -> ValidationReport:
    """Validate ``root`` against :class:`DataLayout`; an empty layout is valid."""
    report = ValidationReport(root=root.resolve())
    if not root.exists():
        report.error(root.as_posix(), "data folder does not exist")
        return report
    layout = DataLayout(report.root)
    _validate_detector(report, layout)
    _validate_ocr(report, layout)
    _validate_eval(report, layout)
    return report


__all__ = ["Issue", "ValidationReport", "validate_data"]
