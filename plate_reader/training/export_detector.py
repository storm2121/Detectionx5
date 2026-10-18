"""Export the YOLOv10 detector to ONNX for torch-free serving and the browser.

Ultralytics writes the ONNX file next to the weights; it is moved to ``models/detector.onnx``.
The graph keeps YOLOv10's NMS-free one-to-one head (``(batch, 300, 6)`` boxes), which
:class:`plate_reader.detector_onnx.OnnxPlateDetector` post-processes.
"""

from __future__ import annotations

import importlib
import shutil
from pathlib import Path


def export_detector(weights: Path, out: Path, imgsz: int = 640, opset: int = 17) -> Path:
    ultralytics = importlib.import_module("ultralytics")
    model = ultralytics.YOLO(str(weights))
    # nms=False is what makes Ultralytics export YOLOv10's NMS-free one-to-one head (the
    # exporter sets ``end2end = nms is False``); the default exports the one-to-many head,
    # which needs NMS and would not match the PyTorch path (``predict(nms=False)``).
    # dynamic=True lets the ONNX detector take the same minimum-rectangle letterbox the
    # PyTorch predictor uses, so both runtimes see identical inputs.
    produced = Path(
        model.export(
            format="onnx", imgsz=imgsz, opset=opset, dynamic=True, simplify=False, nms=False
        )
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    if produced.resolve() != out.resolve():
        shutil.move(str(produced), str(out))
    return out


__all__ = ["export_detector"]
