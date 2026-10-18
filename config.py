"""Project-wide settings (compatibility shim).

The settings now live in :mod:`plate_reader.settings`, typed and validated with
pydantic-settings. This module keeps the old constant names so scripts written against
``import config`` keep working. Every value can still be overridden with the same
``PLATE_*`` environment variables.
"""

from __future__ import annotations

from plate_reader.settings import (
    CROP_PADDING,
    DUPLICATE_IOU,
    OCR_LANGUAGES,
    OCR_UPSCALE,
    PROJECT_ROOT,
    get_settings,
)

_settings = get_settings()

# --- paths -----------------------------------------------------------------
MODEL_PATH = _settings.model
OUTPUT_DIR = _settings.output_dir
SAMPLES_DIR = PROJECT_ROOT / "samples"

# --- detection -------------------------------------------------------------
DETECTION_CONF = _settings.conf

# --- OCR -------------------------------------------------------------------
OCR_USE_GPU = _settings.gpu

__all__ = [
    "CROP_PADDING",
    "DETECTION_CONF",
    "DUPLICATE_IOU",
    "MODEL_PATH",
    "OCR_LANGUAGES",
    "OCR_UPSCALE",
    "OCR_USE_GPU",
    "OUTPUT_DIR",
    "PROJECT_ROOT",
    "SAMPLES_DIR",
]
