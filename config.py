"""Project-wide settings.

Every path is derived from the location of this file, so the project runs
from wherever it is cloned. Anything worth changing can be overridden with
an environment variable instead of editing source.
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def _path_from_env(var: str, default: Path) -> Path:
    raw = os.getenv(var)
    return Path(raw).expanduser().resolve() if raw else default


def _float_from_env(var: str, default: float) -> float:
    try:
        return float(os.environ[var])
    except (KeyError, ValueError):
        return default


# --- paths -----------------------------------------------------------------
MODEL_PATH = _path_from_env("PLATE_MODEL", PROJECT_ROOT / "models" / "best.pt")
OUTPUT_DIR = _path_from_env("PLATE_OUTPUT_DIR", PROJECT_ROOT / "output")
SAMPLES_DIR = PROJECT_ROOT / "samples"

# --- detection -------------------------------------------------------------
DETECTION_CONF = _float_from_env("PLATE_CONF", 0.25)

# YOLOv10 is NMS-free and occasionally emits two near-identical boxes for the
# same plate; anything overlapping more than this is treated as a duplicate.
DUPLICATE_IOU = 0.6

# Plates are cropped tight by the detector. A little padding keeps the first
# and last glyph from being clipped, which matters a lot at this resolution.
CROP_PADDING = 0.08

# --- OCR -------------------------------------------------------------------
OCR_LANGUAGES = ("ar", "en")
OCR_USE_GPU = os.getenv("PLATE_GPU", "0") == "1"

# Crops come out around 70x25 px, far too small to read directly.
OCR_UPSCALE = 4
