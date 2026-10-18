"""Plate detection with the fine-tuned YOLOv10 model."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .imaging import Image, as_u8
from .settings import CROP_PADDING, DUPLICATE_IOU, get_settings

Box = tuple[int, int, int, int]


@dataclass
class Detection:
    """One detected plate and the pixels it covers."""

    box: Box
    confidence: float
    crop: Image


def _load_model(model_path: Path) -> Any:
    """Load the weights under either ultralytics distribution.

    The THU-MIG YOLOv10 fork exposes a dedicated ``YOLOv10`` class and its ``YOLO``
    class cannot post-process these weights. Stock ultralytics 8.2+ reads them through
    ``YOLO`` and has no ``YOLOv10``. Try the fork first.
    """
    module = importlib.import_module("ultralytics")
    model_class = getattr(module, "YOLOv10", None) or module.YOLO
    return model_class(str(model_path))


def iou(a: Box, b: Box) -> float:
    """Intersection over union of two ``(x1, y1, x2, y2)`` boxes."""
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


# Kept under its historical private name for callers that imported it.
_iou = iou


def deduplicate(detections: list[Detection]) -> list[Detection]:
    """Drop near-identical boxes, keeping the most confident of each cluster."""
    kept: list[Detection] = []
    for candidate in sorted(detections, key=lambda d: d.confidence, reverse=True):
        if all(iou(candidate.box, k.box) < DUPLICATE_IOU for k in kept):
            kept.append(candidate)
    return kept


_deduplicate = deduplicate


def pad_box(box: list[float] | tuple[float, ...], width: int, height: int) -> Box:
    """Grow a box by :data:`CROP_PADDING` on each side, clipped to the image."""
    x1, y1, x2, y2 = box
    pad_x = (x2 - x1) * CROP_PADDING
    pad_y = (y2 - y1) * CROP_PADDING
    return (
        max(0, int(x1 - pad_x)),
        max(0, int(y1 - pad_y)),
        min(width, int(x2 + pad_x)),
        min(height, int(y2 + pad_y)),
    )


def detections_from_boxes(
    image: Image, boxes: list[list[float]], scores: list[float]
) -> list[Detection]:
    """Pad, crop and de-duplicate raw boxes; shared by the PyTorch and ONNX detectors."""
    height, width = image.shape[:2]
    detections: list[Detection] = []
    for box, score in zip(boxes, scores, strict=True):
        x1, y1, x2, y2 = pad_box(box, width, height)
        if x2 <= x1 or y2 <= y1:
            continue
        detections.append(
            Detection(
                box=(x1, y1, x2, y2), confidence=float(score), crop=image[y1:y2, x1:x2].copy()
            )
        )
    return deduplicate(detections)


class PlateDetector:
    """Wraps the YOLO model and returns padded crops ready for OCR."""

    def __init__(
        self,
        model_path: Path | str | None = None,
        confidence: float | None = None,
    ) -> None:
        settings = get_settings()
        self.model_path = Path(model_path or settings.model)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model weights not found at {self.model_path}. "
                "Set PLATE_MODEL to point at your .pt file."
            )
        self.confidence = settings.conf if confidence is None else confidence
        self._model = _load_model(self.model_path)

    def detect(self, image_path: Path | str) -> list[Detection]:
        """Detect every plate in one image, most confident first."""
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Newer Ultralytics defaults to the one-to-many head with external NMS. These
        # YOLOv10 weights use the NMS-free one-to-one head; selecting it explicitly
        # preserves the trained detector's boxes across versions.
        results = self._model.predict(
            str(image_path), conf=self.confidence, verbose=False, nms=False
        )
        if not results:
            return []

        return self._detections(results)

    def detect_image(self, image: Image) -> list[Detection]:
        """Detect plates in an in-memory BGR image (the service and video jobs use this)."""
        results = self._model.predict(image, conf=self.confidence, verbose=False, nms=False)
        return self._detections(results) if results else []

    @staticmethod
    def _detections(results: Any) -> list[Detection]:
        result = results[0]
        original = as_u8(result.orig_img)
        boxes: list[list[float]] = result.boxes.xyxy.tolist()
        scores: list[float] = result.boxes.conf.tolist()
        return detections_from_boxes(original, boxes, scores)


__all__ = [
    "Box",
    "Detection",
    "PlateDetector",
    "deduplicate",
    "detections_from_boxes",
    "iou",
    "pad_box",
]
