"""Image preparation for OCR.

A detected plate is only around 70x25 pixels, which no OCR engine reads
reliably. Rather than guess at one perfect enhancement, each crop is expanded
into several differently-processed versions; the pipeline reads all of them
and votes on the answer. Different treatments fail on different plates, so
the ensemble is noticeably more robust than any single variant.
"""
from __future__ import annotations

import cv2
import numpy as np

import config


def _upscale(image: np.ndarray, factor: int) -> np.ndarray:
    height, width = image.shape[:2]
    return cv2.resize(
        image,
        (width * factor, height * factor),
        interpolation=cv2.INTER_CUBIC,
    )


def build_variants(crop: np.ndarray) -> list[tuple[str, np.ndarray]]:
    """Return named, OCR-ready renderings of one plate crop."""
    if crop is None or crop.size == 0:
        return []

    enlarged = _upscale(crop, config.OCR_UPSCALE)
    grey = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)

    variants: list[tuple[str, np.ndarray]] = [
        ("colour", enlarged),
        ("grey", grey),
    ]

    # Local contrast, which lifts glyphs out of a washed-out or shadowed plate.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrasted = clahe.apply(grey)
    variants.append(("clahe", contrasted))

    # Denoised binarisation: good on clean, well-lit plates.
    blurred = cv2.GaussianBlur(contrasted, (3, 3), 0)
    _, otsu = cv2.threshold(
        blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
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
    variants.append(("adaptive", adaptive))

    # Some plates photograph as light-on-dark; give the engine that reading too.
    variants.append(("otsu_inverted", cv2.bitwise_not(otsu)))

    # Mild sharpening recovers edges softened by the upscale.
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    variants.append(("sharpened", cv2.filter2D(contrasted, -1, kernel)))

    return variants


def build_field_variants(field: np.ndarray) -> list[tuple[str, np.ndarray]]:
    """Variants for a single already-scaled field.

    Fields arrive from :mod:`plate_reader.segment` at a workable size, so this
    skips the upscale and only varies the thresholding.
    """
    if field is None or field.size == 0:
        return []

    grey = (
        cv2.cvtColor(field, cv2.COLOR_BGR2GRAY) if field.ndim == 3 else field
    )
    contrasted = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(grey)

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
        ("field_otsu", otsu),
        ("field_adaptive", adaptive),
        ("field_sharp", cv2.filter2D(contrasted, -1,
                                     np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]]))),
    ]
