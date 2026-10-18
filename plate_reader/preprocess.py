"""Image preparation for OCR.

A detected plate is only around 70x25 pixels, which no OCR engine reads reliably.
Rather than guess at one perfect enhancement, each crop is expanded into several
differently-processed versions; the pipeline reads all of them and votes on the
answer. Different treatments fail on different plates, so the ensemble is noticeably
more robust than any single variant.
"""

from __future__ import annotations

import cv2
import numpy as np

from .imaging import Image, as_u8
from .settings import OCR_UPSCALE

_SHARPEN = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])


def _upscale(image: Image, factor: int) -> Image:
    height, width = image.shape[:2]
    return as_u8(
        cv2.resize(image, (width * factor, height * factor), interpolation=cv2.INTER_CUBIC)
    )


def build_variants(crop: Image | None) -> list[tuple[str, Image]]:
    """Return named, OCR-ready renderings of one plate crop."""
    if crop is None or crop.size == 0:
        return []

    enlarged = _upscale(crop, OCR_UPSCALE)
    grey = as_u8(cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY))

    variants: list[tuple[str, Image]] = [
        ("colour", enlarged),
        ("grey", grey),
    ]

    # Local contrast, which lifts glyphs out of a washed-out or shadowed plate.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrasted = as_u8(clahe.apply(grey))
    variants.append(("clahe", contrasted))

    # Denoised binarisation: good on clean, well-lit plates.
    blurred = cv2.GaussianBlur(contrasted, (3, 3), 0)
    _, otsu_raw = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    otsu = as_u8(otsu_raw)
    variants.append(("otsu", otsu))

    # Adaptive threshold: better when lighting falls off across the plate.
    adaptive = cv2.adaptiveThreshold(
        contrasted,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=9,
    )
    variants.append(("adaptive", as_u8(adaptive)))

    # Some plates photograph as light-on-dark; give the engine that reading too.
    variants.append(("otsu_inverted", as_u8(cv2.bitwise_not(otsu))))

    # Mild sharpening recovers edges softened by the upscale.
    variants.append(("sharpened", as_u8(cv2.filter2D(contrasted, -1, _SHARPEN))))

    return variants


def build_field_variants(field: Image | None) -> list[tuple[str, Image]]:
    """Variants for a single already-scaled field.

    Fields arrive from :mod:`plate_reader.segment` at a workable size, so this skips
    the upscale and only varies the thresholding.
    """
    if field is None or field.size == 0:
        return []

    grey = as_u8(cv2.cvtColor(field, cv2.COLOR_BGR2GRAY)) if field.ndim == 3 else field
    contrasted = as_u8(cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(grey))

    _, otsu = cv2.threshold(
        cv2.GaussianBlur(contrasted, (3, 3), 0),
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )

    adaptive = cv2.adaptiveThreshold(
        contrasted,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=41,
        C=11,
    )

    return [
        ("field", field),
        ("field_clahe", contrasted),
        ("field_otsu", as_u8(otsu)),
        ("field_adaptive", as_u8(adaptive)),
        ("field_sharp", as_u8(cv2.filter2D(contrasted, -1, _SHARPEN))),
    ]


__all__ = ["build_field_variants", "build_variants"]
