"""Where real data goes. The paths here are the contract ``docs/insert_your_own_data.md`` documents.

::

    data/
    ├── README.md
    ├── detector.yaml                      # Ultralytics dataset file (one class: LP)
    ├── detector/
    │   ├── images/{train,val}/*.jpg|png   # full photos
    │   └── labels/{train,val}/*.txt       # YOLO boxes: "0 cx cy w h", normalised
    ├── ocr/
    │   ├── train/labels.csv               # crop_path,plate_text,format
    │   └── val/labels.csv
    └── eval/
        └── labels.csv                     # image_path,plate_text,format,x1,y1,x2,y2
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

SPLITS: Final = ("train", "val")
IMAGE_SUFFIXES: Final = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".webp"})
OCR_COLUMNS: Final = ("crop_path", "plate_text", "format")
EVAL_COLUMNS: Final = ("image_path", "plate_text", "format", "x1", "y1", "x2", "y2")
DETECTOR_CLASS_NAMES: Final = ("LP",)


@dataclass(frozen=True)
class DataLayout:
    """Resolved paths of the data folder."""

    root: Path

    @property
    def detector_yaml(self) -> Path:
        return self.root / "detector.yaml"

    def detector_images(self, split: str) -> Path:
        return self.root / "detector" / "images" / split

    def detector_labels(self, split: str) -> Path:
        return self.root / "detector" / "labels" / split

    def ocr_labels(self, split: str) -> Path:
        return self.root / "ocr" / split / "labels.csv"

    @property
    def eval_labels(self) -> Path:
        return self.root / "eval" / "labels.csv"

    def directories(self) -> list[Path]:
        """Every folder of the layout, for creating an empty skeleton."""
        dirs = [self.root / "eval"]
        for split in SPLITS:
            dirs += [self.detector_images(split), self.detector_labels(split)]
            dirs.append(self.ocr_labels(split).parent)
        return dirs


__all__ = [
    "DETECTOR_CLASS_NAMES",
    "EVAL_COLUMNS",
    "IMAGE_SUFFIXES",
    "OCR_COLUMNS",
    "SPLITS",
    "DataLayout",
]
