"""Split a plate crop into its three printed fields.

A Moroccan civilian plate is laid out as ``24830 | ب | 1`` — a digit block,
an Arabic letter, and a region code, divided by two printed vertical bars.

Those bars are the reason naive OCR does so badly here: engines read them as
an Arabic alif or as the digit ``1``, which corrupts every field at once. They
are, however, easy to find geometrically — they are the only marks that are
tall and extremely narrow. Locating them lets each field be cropped and read
on its own, with an alphabet appropriate to that field.

Segmentation is best-effort. When the bars cannot be found the caller falls
back to reading the plate as a whole.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# A separator is at least this tall relative to the plate body...
SEPARATOR_MIN_HEIGHT = 0.30
# ...and no wider than this relative to its own height.
SEPARATOR_MAX_ASPECT = 0.22
# Components taller than this are plate borders or shadows, not glyphs.
GLYPH_MAX_HEIGHT = 0.95
# Components wider than this span several characters and are not separators.
GLYPH_MAX_WIDTH = 0.30

WORKING_UPSCALE = 6


@dataclass
class PlateFields:
    """The three printed fields of a plate, as images."""

    plate: np.ndarray
    digits: np.ndarray | None = None
    letter: np.ndarray | None = None
    region: np.ndarray | None = None

    @property
    def is_complete(self) -> bool:
        return all(
            field is not None and field.size > 0
            for field in (self.digits, self.letter, self.region)
        )


def _enhance(image: np.ndarray) -> np.ndarray:
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(grey)


def isolate_plate(crop: np.ndarray) -> np.ndarray:
    """Trim the detector's crop down to the bright plate body.

    YOLO boxes carry a little bodywork with them, which drags the threshold
    around and adds spurious components. The plate itself is the largest
    bright blob in the crop.
    """
    enhanced = _enhance(crop)
    _, bright = cv2.threshold(
        cv2.GaussianBlur(enhanced, (5, 5), 0),
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))

    count, _, stats, _ = cv2.connectedComponentsWithStats(bright, 8)
    if count <= 1:
        return crop

    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h = stats[largest, :4]

    # Ignore an implausible "plate" that is a highlight rather than the plate.
    if w < crop.shape[1] * 0.4 or h < crop.shape[0] * 0.3:
        return crop
    return crop[y : y + h, x : x + w]


def _find_separators(plate: np.ndarray) -> list[tuple[int, int]]:
    """Return (x, width) for each printed separator bar, left to right."""
    enhanced = _enhance(plate)
    _, binary = cv2.threshold(
        cv2.GaussianBlur(enhanced, (3, 3), 0),
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )

    height, width = binary.shape
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)

    separators: list[tuple[int, int]] = []
    for index in range(1, count):
        x, _, w, h, area = stats[index]
        if h < height * SEPARATOR_MIN_HEIGHT or h > height * GLYPH_MAX_HEIGHT:
            continue
        if w > width * GLYPH_MAX_WIDTH or w < 2 or area < 20:
            continue
        if w / h < SEPARATOR_MAX_ASPECT:
            separators.append((int(x), int(w)))

    separators.sort()
    return separators


def segment_fields(crop: np.ndarray) -> PlateFields | None:
    """Split a plate crop into digit / letter / region images.

    Returns ``None`` when the crop is unusable, and a :class:`PlateFields`
    with missing parts when the separators could not be located — callers
    should check :attr:`PlateFields.is_complete` before relying on the fields.
    """
    if crop is None or crop.size == 0:
        return None

    plate = isolate_plate(crop)
    plate = cv2.resize(
        plate,
        (plate.shape[1] * WORKING_UPSCALE, plate.shape[0] * WORKING_UPSCALE),
        interpolation=cv2.INTER_CUBIC,
    )

    separators = _find_separators(plate)
    fields = PlateFields(plate=plate)
    if len(separators) < 2:
        return fields

    # With more than two candidates, the outermost pair brackets the letter.
    first, last = separators[0], separators[-1]
    left_cut = first[0] + first[1] // 2
    right_cut = last[0] + last[1] // 2

    width = plate.shape[1]
    minimum = width * 0.03
    if left_cut < minimum or right_cut > width - minimum or right_cut - left_cut < minimum:
        return fields

    fields.digits = plate[:, : max(0, left_cut - first[1])]
    fields.letter = plate[:, left_cut + first[1] : right_cut - last[1]]
    fields.region = plate[:, right_cut + last[1] :]
    return fields


def tighten(field: np.ndarray) -> np.ndarray:
    """Crop a field down to the glyphs it actually contains.

    Fields are cut as full-height strips, so a short glyph such as ``ب`` sits
    in a tall, mostly empty frame. Scaling that frame to a fixed height leaves
    the glyph tiny and unreadable; cropping to the ink first means the glyph
    fills the image it is finally recognised from.
    """
    if field is None or field.size == 0:
        return field

    grey = _enhance(field)
    _, binary = cv2.threshold(
        cv2.GaussianBlur(grey, (3, 3), 0),
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )

    height, width = binary.shape
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)

    boxes = []
    for index in range(1, count):
        x, y, w, h, area = stats[index]
        if area < 8:
            continue
        # The plate border and the shadow under it run off the top or bottom
        # of the strip; printed glyphs always sit clear of both.
        if y <= 1 or y + h >= height - 1:
            continue
        # A wide, short blob is the painted rim, not a character.
        if w > width * 0.85 and h < height * 0.40:
            continue
        boxes.append((x, y, x + w, y + h))

    if not boxes:
        return field

    # Crop rows only. Trimming columns as well would reduce a lone region
    # digit to a sliver that EasyOCR's text detector refuses to look at,
    # whereas the vertical crop is what actually rescues a short glyph.
    y0 = min(b[1] for b in boxes)
    y1 = max(b[3] for b in boxes)

    pad_y = max(2, int((y1 - y0) * 0.12))
    y0, y1 = max(0, y0 - pad_y), min(height, y1 + pad_y)

    if y1 - y0 < 3:
        return field
    return field[y0:y1, :]


def prepare_for_ocr(
    field: np.ndarray,
    target_height: int = 160,
    margin: int = 40,
    tighten_first: bool = False,
) -> np.ndarray | None:
    """Scale a field up and float it on a white margin.

    EasyOCR's text detector needs whitespace around a mark to find it at all,
    which is exactly what a tightly cropped field lacks.

    ``tighten_first`` is for the letter field only. The letter is a short glyph
    adrift in a full-height strip, so it has to be cropped to its ink or the
    scaling leaves it too small to recognise. The digit fields already fill
    their strips vertically, and cropping them measurably hurts accuracy.
    """
    if field is None or field.size == 0 or min(field.shape[:2]) < 3:
        return None

    if tighten_first:
        field = tighten(field)
        if field.size == 0 or min(field.shape[:2]) < 3:
            return None

    height = field.shape[0]
    scale = target_height / height
    resized = cv2.resize(
        field,
        (max(1, int(field.shape[1] * scale)), target_height),
        interpolation=cv2.INTER_CUBIC,
    )

    white = (255, 255, 255) if resized.ndim == 3 else 255
    return cv2.copyMakeBorder(
        resized, margin, margin, margin, margin, cv2.BORDER_CONSTANT, value=white
    )
