"""Parity fixtures: what the Python pipeline outputs on a fixed set of synthetic crops.

``results/parity_fixtures.json`` records, for each fixture PNG under
``tests/fixtures/parity/``, the CRNN logits, the greedy string, the constrained beam with
calibrated probabilities and the conformal set, and under ``scenes`` the end-to-end
fixtures of :mod:`plate_reader.parity`. The PyTorch-versus-ONNX test checks the committed
model against it, and the browser runtime must reproduce it within the stated tolerances.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Final

import cv2
import numpy as np

from ..imaging import as_u8
from ..synthetic.generate import make_crop
from ..synthetic.splits import SPLIT_SEEDS
from ..synthetic.writer import encode_png
from .preprocess import INPUT_HEIGHT, INPUT_WIDTH, to_grey
from .runtime import CRNNRuntime

FIXTURE_SEED: Final = SPLIT_SEEDS["test"]
FIXTURE_COUNT: Final = 16
TOLERANCE: Final = {"logits": 1e-3, "probability": 1e-4}


def model_input(image: np.ndarray, height: int = INPUT_HEIGHT, width: int = INPUT_WIDTH) -> str:
    """The 8-bit grey model input of ``preprocess`` (before scaling), base64-encoded."""
    grey = to_grey(as_u8(image))
    shrinking = grey.shape[0] > height or grey.shape[1] > width
    resized = cv2.resize(
        grey, (width, height), interpolation=cv2.INTER_AREA if shrinking else cv2.INTER_LINEAR
    )
    return base64.b64encode(np.ascontiguousarray(resized).tobytes()).decode("ascii")


def write_fixtures(
    runtime: CRNNRuntime,
    image_dir: Path,
    json_path: Path,
    root: Path,
    count: int = FIXTURE_COUNT,
    scenes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write the crop fixtures, plus the end-to-end ``scenes`` of :mod:`plate_reader.parity`."""
    image_dir.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for index in range(count):
        sample = make_crop(FIXTURE_SEED, index)
        path = image_dir / f"crnn_{index:02d}.png"
        path.write_bytes(encode_png(sample.image))
        # Read the PNG back so every runtime starts from the same decoded pixels.
        image = as_u8(cv2.imread(str(path), cv2.IMREAD_COLOR))
        logits = runtime.logits([image])[0]
        beam = runtime.decode(logits, "beam", alpha=0.1)
        greedy = runtime.decode(logits, "greedy", alpha=None)
        fixtures.append(
            {
                "image": path.relative_to(root).as_posix(),
                "truth": sample.tokens,
                "input": model_input(image),
                "logits": np.round(logits.astype(np.float64), 6).tolist(),
                "greedy": greedy.prediction,
                "beam": [[h.tokens, round(h.probability, 8)] for h in beam.hypotheses],
                "prediction": beam.prediction,
                "confidence": round(beam.confidence, 8) if beam.confidence is not None else None,
                "prediction_set": list(beam.prediction_set)
                if beam.prediction_set is not None
                else None,
            }
        )
    payload = {
        "schema": "detectionx5.parity/1",
        "label": "synthetic fixtures; synthetic results are not real-world accuracy",
        "model_version": runtime.version,
        "temperature": runtime.metadata.temperature,
        "beam_width": runtime.metadata.beam_width,
        "alpha": 0.1,
        "input": runtime.metadata.input,
        "tolerance": TOLERANCE,
        "fixtures": fixtures,
    }
    if scenes is not None:
        payload["scenes"] = scenes
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return payload


__all__ = ["FIXTURE_COUNT", "FIXTURE_SEED", "TOLERANCE", "write_fixtures"]
