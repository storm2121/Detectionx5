"""What the browser runtime needs from Python: the plate automaton and OpenCV references.

``plate export web`` writes

- ``apps/dashboard/src/inference/grammar.json``: the minimal plate DFA and the CRNN class
  order, so the TypeScript constrained beam search walks exactly the automaton the Python
  decoder walks (a test fails when the committed copy drifts from the grammar);
- ``tests/fixtures/web/opencv_cases.json``: small deterministic images with what
  ``cv2.cvtColor`` and ``cv2.resize`` (INTER_LINEAR and INTER_AREA, one and three channels,
  growing, shrinking, mixed and exact integer factors) make of them. The dashboard's unit
  tests require its TypeScript ports to reproduce every byte.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Final

import cv2
import numpy as np

from .grammar import GRAMMAR
from .imaging import as_u8
from .settings import PROJECT_ROOT

GRAMMAR_JSON: Final = PROJECT_ROOT / "apps" / "dashboard" / "src" / "inference" / "grammar.json"
OPENCV_CASES: Final = PROJECT_ROOT / "tests" / "fixtures" / "web" / "opencv_cases.json"

#: (source width, source height, target width, target height, channels, interpolation)
RESIZE_CASES: Final[tuple[tuple[int, int, int, int, int, str], ...]] = (
    # The CRNN input (160 x 32) from crops of every shape the detector produces.
    (98, 28, 160, 32, 1, "linear"),  # grows both ways
    (7, 5, 160, 32, 1, "linear"),  # tiny
    (400, 96, 160, 32, 1, "area"),  # shrinks both ways
    (321, 64, 160, 32, 1, "area"),  # shrinks by a fraction
    (320, 64, 160, 32, 1, "area"),  # exactly by two: OpenCV's 2x2 average
    (480, 96, 160, 32, 1, "area"),  # exactly by three
    (140, 60, 160, 32, 1, "area"),  # taller only: area-flavoured bilinear
    (300, 20, 160, 32, 1, "area"),  # wider only
    (161, 33, 160, 32, 1, "area"),  # barely shrinks
    (160, 32, 160, 32, 1, "area"),  # unchanged
    # Letterboxing a photo for the detector (three channels, any size).
    (64, 48, 51, 38, 3, "linear"),  # shrinks by a fraction
    (40, 30, 64, 48, 3, "linear"),  # grows
    (64, 48, 32, 24, 3, "linear"),  # exactly by two
    (37, 23, 50, 17, 3, "linear"),  # odd sizes: SIMD tail of the vertical pass
    (101, 77, 61, 45, 1, "linear"),  # odd sizes, one channel
    (59, 41, 23, 19, 3, "area"),  # three-channel area
)


#: Extra random shapes (seeded): borders, tiny images and odd widths for both interpolations.
RANDOM_CASES: Final = 24


def _random_cases(rng: np.random.Generator) -> list[tuple[int, int, int, int, int, str]]:
    cases = []
    for _ in range(RANDOM_CASES):
        sw, sh, dw, dh = (int(v) for v in rng.integers(3, 97, size=4))
        channels = int(rng.choice([1, 3]))
        interpolation = str(rng.choice(["linear", "area"]))
        cases.append((sw, sh, dw, dh, channels, interpolation))
    return cases


def grammar_export() -> dict[str, Any]:
    from .crnn.charset import CHARSET_ID, CLASSES

    return {**GRAMMAR.as_dict(), "charset": list(CLASSES), "charset_id": CHARSET_ID}


def _b64(array: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(array).tobytes()).decode("ascii")


def _image(rng: np.random.Generator, width: int, height: int, channels: int) -> np.ndarray:
    """Smooth gradients plus noise: every interpolation weight and rounding case shows up."""
    y, x = np.mgrid[0:height, 0:width]
    base = (x * 255.0 / max(1, width - 1) + y * 97.0 / max(1, height - 1)) % 256
    shape = (height, width, channels) if channels == 3 else (height, width)
    noise = rng.integers(-40, 41, size=shape)
    stacked = np.stack([base, 255 - base, (base * 3) % 256], axis=-1) if channels == 3 else base
    return as_u8(np.clip(stacked + noise, 0, 255).astype(np.uint8))


def opencv_cases(seed: int = 0) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    resizes = []
    for sw, sh, dw, dh, channels, interpolation in (*RESIZE_CASES, *_random_cases(rng)):
        src = _image(rng, sw, sh, channels)
        flag = cv2.INTER_LINEAR if interpolation == "linear" else cv2.INTER_AREA
        out = cv2.resize(src, (dw, dh), interpolation=flag)
        resizes.append(
            {
                "source": [sw, sh, channels],
                "target": [dw, dh],
                "interpolation": interpolation,
                "src": _b64(src),
                "expected": _b64(out),
            }
        )
    colour = _image(rng, 33, 17, 3)
    grey = cv2.cvtColor(colour, cv2.COLOR_BGR2GRAY)
    return {
        "schema": "detectionx5.opencv_cases/1",
        "opencv": cv2.__version__,
        "resize": resizes,
        "grey": {"size": [33, 17], "src": _b64(colour), "expected": _b64(grey)},
    }


def write_web_assets(
    grammar_path: Path = GRAMMAR_JSON, cases_path: Path = OPENCV_CASES
) -> list[Path]:
    grammar_path.parent.mkdir(parents=True, exist_ok=True)
    grammar_path.write_text(
        json.dumps(grammar_export(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    cases_path.parent.mkdir(parents=True, exist_ok=True)
    cases_path.write_text(json.dumps(opencv_cases(), indent=1) + "\n", encoding="utf-8")
    return [grammar_path, cases_path]


__all__ = ["GRAMMAR_JSON", "OPENCV_CASES", "grammar_export", "opencv_cases", "write_web_assets"]
