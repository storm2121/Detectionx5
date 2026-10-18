"""End-to-end parity fixtures: several synthetic street photos of one car, read and fused.

``plate export fixtures`` stores, next to the CRNN crop fixtures of
:mod:`plate_reader.crnn.parity`, one synthetic multi-view set (``tests/fixtures/parity/
scene_*.png``: the same plate photographed in different street scenes) and what the Python
pipeline makes of it: for every photo the detector's raw boxes, the padded crop box, the
constrained-beam posterior and that view's conformal set; for the set, the fused posterior,
the per-character posteriors, the calibrated confidence and the conformal set at the
service's level. The browser runtime must reproduce all of it, and the dashboard's samples
and end-to-end smoke test use the same photos.

The set is the first one in which the detector finds a plate in every photo; it is kept
whether or not the read is right, because parity is about reproducing the Python pipeline,
not about accuracy (and these are synthetic images: not real-world accuracy).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import cv2
import numpy as np

from .crnn.runtime import file_version
from .imaging import as_u8
from .settings import CROP_PADDING
from .synthetic.generate import make_scene_views
from .synthetic.splits import SPLIT_SEEDS
from .synthetic.writer import encode_png

SCENE_VIEWS: Final = 3
SCENE_ALPHA: Final = 0.05
SCENE_SEED: Final = SPLIT_SEEDS["test"]
SCENE_LIMIT: Final = 50


def _round(values: list[tuple[str, float]], digits: int = 8) -> list[list[Any]]:
    return [[tokens, round(float(p), digits)] for tokens, p in values]


def write_scene_fixtures(
    crnn_path: Path,
    detector_path: Path,
    image_dir: Path,
    root: Path,
    views: int = SCENE_VIEWS,
) -> dict[str, Any]:
    """Write the first test-seed multi-view scene set whose every photo has a detection."""
    from .detector_onnx import PAD_VALUE, OnnxPlateDetector
    from .eval.recognizers import CRNNRecognizer
    from .pipeline import PlatePipeline

    detector = OnnxPlateDetector(detector_path)
    recognizer = CRNNRecognizer("beam", crnn_path, alpha=SCENE_ALPHA)
    pipeline = PlatePipeline(recognizer, detector)
    for index in range(SCENE_LIMIT):
        samples = make_scene_views(SCENE_SEED, index, views)
        encoded = [encode_png(sample.image) for sample in samples]
        # Decode the PNGs again so every runtime starts from the same pixels.
        images = [
            as_u8(cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)) for data in encoded
        ]
        raw = [detector.raw_boxes(image) for image in images]
        if all(scores for _, scores in raw):
            break
    else:
        raise RuntimeError(f"no set among {SCENE_LIMIT} has a detection in every photo")

    result = pipeline.read(images)
    image_dir.mkdir(parents=True, exist_ok=True)
    out_views: list[dict[str, Any]] = []
    for number, (sample, data, image, (boxes, scores), view) in enumerate(
        zip(samples, encoded, images, raw, result.views, strict=True)
    ):
        path = image_dir / f"scene_{number:02d}.png"
        path.write_bytes(data)
        read = view.read
        detection = view.detection
        assert read is not None
        assert detection is not None
        out_views.append(
            {
                "image": path.relative_to(root).as_posix(),
                "height": int(image.shape[0]),
                "width": int(image.shape[1]),
                "truth_box": list(sample.plates[0][1]),
                "detections": [
                    [*(round(float(v), 4) for v in box), round(float(score), 6)]
                    for box, score in zip(boxes, scores, strict=True)
                ],
                "crop_box": [int(v) for v in detection.box],
                "detector_confidence": round(float(detection.confidence), 6),
                "weight": view.weight,
                "prediction": read.prediction,
                "confidence": round(float(read.confidence), 8)
                if read.confidence is not None
                else None,
                "hypotheses": _round([(h.tokens, h.probability) for h in read.hypotheses]),
                "prediction_set": list(read.prediction_set)
                if read.prediction_set is not None
                else None,
            }
        )
    fused = result.fused
    proposing = sum(1 for v in result.views if v.read is not None and v.read.hypotheses)
    return {
        "seed": SCENE_SEED,
        "kind": "scene_views",
        "index": index,
        "truth": samples[0].plates[0][0],
        "alpha": SCENE_ALPHA,
        "detector_version": file_version(detector_path),
        "letterbox": {"size": detector.size, "auto": detector.auto, "stride": 32, "pad": PAD_VALUE},
        "confidence_threshold": detector.confidence,
        "crop_padding": CROP_PADDING,
        "fusion": fused.method,
        # The fused set uses the threshold calibrated for the number of views that proposed
        # a plate (the largest calibrated count not above it).
        "proposing_views": proposing,
        "conformal_threshold": recognizer.conformal_threshold_for(proposing),
        "tolerance": {"box": 1.0, "detector_confidence": 1e-3, "probability": 1e-3},
        "views": out_views,
        "fused": {
            "prediction": fused.prediction,
            "confidence": round(float(fused.confidence), 8),
            "posterior": _round(list(fused.posterior)),
            "prediction_set": list(fused.prediction_set)
            if fused.prediction_set is not None
            else None,
            "positions": [
                {
                    "index": p.index,
                    "symbol": p.symbol,
                    "distribution": _round(list(p.distribution)),
                }
                for p in fused.positions
            ],
        },
    }


__all__ = ["SCENE_ALPHA", "SCENE_SEED", "SCENE_VIEWS", "write_scene_fixtures"]
