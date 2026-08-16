"""Offline Moroccan licence-plate detection and reading."""
from __future__ import annotations

from .detector import Detection, PlateDetector
from .normalize import Plate, is_valid_plate, normalize_text, parse_plate
from .ocr import EasyOCRBackend, available_backends, get_backend
from .pipeline import ImageResult, PlateReading, RunResult, read_images
from .preprocess import build_field_variants, build_variants
from .segment import PlateFields, isolate_plate, segment_fields

__version__ = "1.0.0"

__all__ = [
    "Detection",
    "PlateDetector",
    "Plate",
    "parse_plate",
    "is_valid_plate",
    "normalize_text",
    "EasyOCRBackend",
    "get_backend",
    "available_backends",
    "build_variants",
    "build_field_variants",
    "PlateFields",
    "segment_fields",
    "isolate_plate",
    "read_images",
    "RunResult",
    "ImageResult",
    "PlateReading",
]
