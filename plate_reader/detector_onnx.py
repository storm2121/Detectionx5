"""The plate detector through ONNX Runtime (torch-free serving, ADR 0007).

``models/detector.onnx`` is exported from ``models/best.pt`` by ``plate export detector``.
YOLOv10 exports its NMS-free one-to-one head, so the graph already returns at most 300
boxes as ``(x1, y1, x2, y2, score, class)`` in letterboxed input coordinates; this module
only reproduces Ultralytics' letterbox, undoes it, and applies the same padding, cropping
and de-duplication as :class:`plate_reader.detector.PlateDetector`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import cv2
import numpy as np
import numpy.typing as npt

from .detector import Detection, detections_from_boxes
from .imaging import Image, as_u8
from .settings import get_settings

PAD_VALUE: Final = 114


def letterbox(
    image: Image, size: int, auto: bool = False, stride: int = 32
) -> tuple[Image, float, tuple[float, float]]:
    """Resize keeping aspect so the long side is ``size``, then pad (Ultralytics' rule).

    With ``auto`` the padding only reaches the next multiple of ``stride`` (the minimum
    rectangle, which is what Ultralytics' predictor feeds a PyTorch model); without it the
    image is padded to a ``size`` square.
    """
    h, w = image.shape[:2]
    scale = min(size / h, size / w)
    new_w, new_h = round(w * scale), round(h * scale)
    dw, dh = size - new_w, size - new_h
    if auto:
        dw, dh = dw % stride, dh % stride
    half_w, half_h = dw / 2, dh / 2
    resized = (
        image
        if (new_w, new_h) == (w, h)
        else cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    )
    top, bottom = round(half_h - 0.1), round(half_h + 0.1)
    left, right = round(half_w - 0.1), round(half_w + 0.1)
    padded = cv2.copyMakeBorder(
        resized,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=(PAD_VALUE, PAD_VALUE, PAD_VALUE),
    )
    return as_u8(padded), scale, (float(left), float(top))


class OnnxPlateDetector:
    def __init__(self, model_path: Path | str, confidence: float | None = None) -> None:
        import onnxruntime as ort

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"ONNX detector not found at {self.model_path}")
        self.confidence = get_settings().conf if confidence is None else confidence
        options = ort.SessionOptions()
        options.log_severity_level = 3
        self.session = ort.InferenceSession(
            str(self.model_path), options, providers=["CPUExecutionProvider"]
        )
        model_input = self.session.get_inputs()[0]
        self.input_name = model_input.name
        # A dynamic-shape export takes the minimum rectangle, exactly what Ultralytics'
        # predictor feeds the PyTorch model; a fixed export takes a square.
        fixed = isinstance(model_input.shape[2], int)
        self.size = int(model_input.shape[2]) if fixed else 640
        self.auto = not fixed

    def _tensor(self, image: Image) -> tuple[npt.NDArray[np.float32], float, tuple[float, float]]:
        padded, scale, offset = letterbox(image, self.size, auto=self.auto)
        rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        tensor = (rgb.astype(np.float32) / np.float32(255.0)).transpose(2, 0, 1)[None]
        return np.ascontiguousarray(tensor), scale, offset

    def raw_boxes(self, image: Image) -> tuple[list[list[float]], list[float]]:
        """Boxes over the confidence threshold in image coordinates, before padding."""
        tensor, scale, (left, top) = self._tensor(image)
        output = np.asarray(self.session.run(None, {self.input_name: tensor})[0], dtype=np.float64)[
            0
        ]
        keep = output[:, 4] >= self.confidence
        rows = output[keep]
        h, w = image.shape[:2]
        boxes = rows[:, :4].copy()
        boxes[:, [0, 2]] = ((boxes[:, [0, 2]] - left) / scale).clip(0, w)
        boxes[:, [1, 3]] = ((boxes[:, [1, 3]] - top) / scale).clip(0, h)
        return boxes.tolist(), rows[:, 4].tolist()

    def detect_image(self, image: Image) -> list[Detection]:
        boxes, scores = self.raw_boxes(image)
        return detections_from_boxes(image, boxes, scores)

    def detect(self, image_path: Path | str) -> list[Detection]:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"Image not found or unreadable: {image_path}")
        return self.detect_image(as_u8(image))


__all__ = ["OnnxPlateDetector", "letterbox"]
