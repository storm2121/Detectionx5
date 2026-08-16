"""Plate detection with the fine-tuned YOLOv10 model."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

import config


@dataclass
class Detection:
    """One detected plate and the pixels it covers."""

    box: tuple[int, int, int, int]
    confidence: float
    crop: np.ndarray


def _load_model(model_path: Path):
    """Load the weights under either ultralytics distribution.

    The THU-MIG YOLOv10 fork exposes a dedicated ``YOLOv10`` class and its
    ``YOLO`` class cannot post-process these weights. Stock ultralytics 8.2+
    reads them through ``YOLO`` and has no ``YOLOv10``. Try the fork first.
    """
    try:
        from ultralytics import YOLOv10 as model_class
    except ImportError:
        from ultralytics import YOLO as model_class
    return model_class(str(model_path))


def _iou(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    inter_x1, inter_y1 = max(ax1, bx1), max(ay1, by1)
    inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    if inter == 0:
        return 0.0

    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def _deduplicate(detections: list[Detection]) -> list[Detection]:
    """Drop near-identical boxes, keeping the most confident of each cluster."""
    kept: list[Detection] = []
    for candidate in sorted(detections, key=lambda d: d.confidence, reverse=True):
        if all(_iou(candidate.box, k.box) < config.DUPLICATE_IOU for k in kept):
            kept.append(candidate)
    return kept


class PlateDetector:
    """Wraps the YOLO model and returns padded crops ready for OCR."""

    def __init__(
        self,
        model_path: Path | str | None = None,
        confidence: float | None = None,
    ) -> None:
        self.model_path = Path(model_path or config.MODEL_PATH)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model weights not found at {self.model_path}. "
                "Set PLATE_MODEL to point at your .pt file."
            )
        self.confidence = (
            config.DETECTION_CONF if confidence is None else confidence
        )
        self._model = _load_model(self.model_path)

    def detect(self, image_path: Path | str) -> list[Detection]:
        """Detect every plate in one image, most confident first."""
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        results = self._model.predict(
            str(image_path), conf=self.confidence, verbose=False
        )
        if not results:
            return []

        result = results[0]
        original = result.orig_img
        height, width = original.shape[:2]

        detections: list[Detection] = []
        for box, score in zip(
            result.boxes.xyxy.tolist(), result.boxes.conf.tolist()
        ):
            x1, y1, x2, y2 = self._pad(box, width, height)
            if x2 <= x1 or y2 <= y1:
                continue
            detections.append(
                Detection(
                    box=(x1, y1, x2, y2),
                    confidence=float(score),
                    crop=original[y1:y2, x1:x2].copy(),
                )
            )

        return _deduplicate(detections)

    @staticmethod
    def _pad(
        box: list[float], width: int, height: int
    ) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = box
        pad_x = (x2 - x1) * config.CROP_PADDING
        pad_y = (y2 - y1) * config.CROP_PADDING
        return (
            max(0, int(x1 - pad_x)),
            max(0, int(y1 - pad_y)),
            min(width, int(x2 + pad_x)),
            min(height, int(y2 + pad_y)),
        )
