"""Typed configuration for every entry point.

Values come from ``PLATE_*`` environment variables (the names the project has always
used: ``PLATE_MODEL``, ``PLATE_OUTPUT_DIR``, ``PLATE_CONF``, ``PLATE_GPU``) with defaults
derived from the repository root, so the project runs from wherever it is cloned.
Settings are read when :func:`get_settings` is first called rather than at import time,
which lets tests and the service override them through the environment.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT: Final = Path(__file__).resolve().parents[1]

# --- fixed tuning constants (deliberately not environment-configurable) ----------
# YOLOv10 is NMS-free and occasionally emits two near-identical boxes for the same
# plate; anything overlapping more than this is treated as a duplicate.
DUPLICATE_IOU: Final = 0.6
# Plates are cropped tight by the detector. A little padding keeps the first and last
# glyph from being clipped, which matters a lot at this resolution.
CROP_PADDING: Final = 0.08
OCR_LANGUAGES: Final = ("ar", "en")
# Crops come out around 70x25 px, far too small to read directly.
OCR_UPSCALE: Final = 4


class Settings(BaseSettings):
    """Runtime settings; each field maps to ``PLATE_<NAME>`` in the environment."""

    model_config = SettingsConfigDict(env_prefix="PLATE_", extra="ignore")

    model: Path = Field(default=PROJECT_ROOT / "models" / "best.pt", description="detector weights")
    output_dir: Path = Field(default=PROJECT_ROOT / "output", description="crop output")
    conf: float = Field(default=0.25, ge=0.0, le=1.0, description="detection threshold")
    gpu: bool = Field(default=False, description="run EasyOCR on the GPU")
    data_dir: Path = Field(default=PROJECT_ROOT / "data", description="real-data root")
    results_dir: Path = Field(default=PROJECT_ROOT / "results", description="metrics JSON")

    @field_validator("model", "output_dir", "data_dir", "results_dir", mode="after")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings; call ``get_settings.cache_clear()`` after changing the env."""
    return Settings()


__all__ = [
    "CROP_PADDING",
    "DUPLICATE_IOU",
    "OCR_LANGUAGES",
    "OCR_UPSCALE",
    "PROJECT_ROOT",
    "Settings",
    "get_settings",
]
