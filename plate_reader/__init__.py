"""Offline Moroccan licence-plate detection and reading.

The public names below are the ones the CLI, GUI and API shims have always imported;
the platform modules (grammar, synthetic, eval, crnn, fusion) are imported explicitly
from their subpackages so that importing this package stays light.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .detector import Detection, PlateDetector
from .grammar import GRAMMAR, Plate
from .normalize import is_valid_plate, normalize_text, parse_plate
from .ocr import EasyOCRBackend, available_backends, get_backend
from .pipeline import ImageResult, PlateReading, RunResult, read_images
from .preprocess import build_field_variants, build_variants
from .segment import PlateFields, isolate_plate, segment_fields

try:
    __version__ = version("detectionx5")
except PackageNotFoundError:  # pragma: no cover - running from a bare source tree
    __version__ = "0+unknown"

__all__ = [
    "GRAMMAR",
    "Detection",
    "EasyOCRBackend",
    "ImageResult",
    "Plate",
    "PlateDetector",
    "PlateFields",
    "PlateReading",
    "RunResult",
    "__version__",
    "available_backends",
    "build_field_variants",
    "build_variants",
    "get_backend",
    "is_valid_plate",
    "isolate_plate",
    "normalize_text",
    "parse_plate",
    "read_images",
    "segment_fields",
]
