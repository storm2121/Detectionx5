"""Detect plates, read them field by field, and vote on the answer.

The preferred path splits a plate into its three printed fields and reads each
with an alphabet restricted to what that field can contain — digits for the
number and region code, the six legal letters for the middle glyph. Every
field is read from several thresholdings of the same pixels and the results
are pooled, because different treatments fail on different plates.

If the printed separator bars cannot be located the plate is read whole, which
is less accurate but still often correct.

Passing several photographs of one vehicle strengthens the result: agreement
between independent images is much better evidence than one confident read.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path

import numpy as np

from .detector import Detection, PlateDetector
from .normalize import VALID_LETTERS, Plate, normalize_text, parse_plate
from .ocr import OCRBackend, Reading, get_backend
from .preprocess import build_field_variants, build_variants
from .segment import prepare_for_ocr, segment_fields

MAX_MAIN_DIGITS = 5
MAX_REGION_DIGITS = 2


@dataclass
class PlateReading:
    """The verdict for a single detected plate."""

    plate: Plate | None
    detection: Detection
    votes: dict[str, float] = dataclass_field(default_factory=dict)
    components: dict[str, str] = dataclass_field(default_factory=dict)
    segmented: bool = False

    @property
    def text(self) -> str:
        return self.plate.text if self.plate else "unreadable"

    @property
    def score(self) -> float:
        return self.votes.get(self.plate.text, 0.0) if self.plate else 0.0


@dataclass
class ImageResult:
    path: Path
    readings: list[PlateReading] = dataclass_field(default_factory=list)

    @property
    def best(self) -> PlateReading | None:
        readable = [r for r in self.readings if r.plate]
        if readable:
            return max(readable, key=lambda r: (r.score, r.detection.confidence))
        return self.readings[0] if self.readings else None


@dataclass
class RunResult:
    """The outcome of reading one or more images."""

    images: list[ImageResult] = dataclass_field(default_factory=list)
    plate: Plate | None = None
    votes: dict[str, float] = dataclass_field(default_factory=dict)

    @property
    def text(self) -> str:
        return self.plate.text if self.plate else "unreadable"

    @property
    def agreement(self) -> int:
        """How many images independently produced the winning plate."""
        if not self.plate:
            return 0
        return sum(
            1
            for image in self.images
            if image.best
            and image.best.plate
            and image.best.plate.text == self.plate.text
        )


# --- voting helpers --------------------------------------------------------
def _vote_digits(readings: list[Reading], max_length: int) -> tuple[str | None, float]:
    """Pick the most strongly supported digit string of a plausible length."""
    tally: dict[str, float] = defaultdict(float)
    for reading in readings:
        text = normalize_text(reading.text)
        if text.isdigit() and 1 <= len(text) <= max_length:
            tally[text] += max(reading.confidence, 0.01)
    if not tally:
        return None, 0.0
    winner = max(tally, key=tally.get)
    return winner, tally[winner]


def _vote_letter(readings: list[Reading]) -> tuple[str | None, float]:
    """Vote per character, since the engine often emits stray marks alongside."""
    tally: dict[str, float] = defaultdict(float)
    for reading in readings:
        for char in normalize_text(reading.text):
            if char in VALID_LETTERS:
                tally[char] += max(reading.confidence, 0.01)
    if not tally:
        return None, 0.0
    winner = max(tally, key=tally.get)
    return winner, tally[winner]


# --- reading strategies ----------------------------------------------------
def _read_segmented(backend: OCRBackend, crop: np.ndarray) -> PlateReading | None:
    """Read a plate by its three fields. Returns ``None`` if not segmentable."""
    fields = segment_fields(crop)
    if fields is None or not fields.is_complete:
        return None

    digit_readings: list[Reading] = []
    letter_readings: list[Reading] = []
    region_readings: list[Reading] = []

    # Only the letter field is cropped to its ink; see prepare_for_ocr.
    for source, sink, reader, tighten_first in (
        (fields.digits, digit_readings, backend.read_digits, False),
        (fields.letter, letter_readings, backend.read_letters, True),
        (fields.region, region_readings, backend.read_digits, False),
    ):
        prepared = prepare_for_ocr(source, tighten_first=tighten_first)
        if prepared is None:
            continue
        for _, variant in build_field_variants(prepared):
            sink.extend(reader(variant))

    digits, digit_score = _vote_digits(digit_readings, MAX_MAIN_DIGITS)
    letter, letter_score = _vote_letter(letter_readings)
    region, region_score = _vote_digits(region_readings, MAX_REGION_DIGITS)

    components = {
        "digits": digits or "?",
        "letter": letter or "?",
        "region": region or "?",
    }
    if not (digits and letter and region):
        return PlateReading(
            plate=None,
            detection=None,  # filled in by the caller
            components=components,
            segmented=True,
        )

    plate = parse_plate(f"{digits}-{letter}-{region}")
    score = digit_score + letter_score + region_score
    return PlateReading(
        plate=plate,
        detection=None,
        votes={plate.text: score} if plate else {},
        components=components,
        segmented=True,
    )


def _read_whole(backend: OCRBackend, crop: np.ndarray) -> PlateReading:
    """Read the plate as a single line — the fallback path."""
    tally: dict[str, float] = defaultdict(float)
    for _, variant in build_variants(crop):
        for restrict in (True, False):
            for reading in backend.read(variant, restrict=restrict):
                parsed = parse_plate(reading.text)
                if parsed is not None:
                    tally[parsed.text] += max(reading.confidence, 0.01)

    winner = max(tally, key=tally.get) if tally else None
    return PlateReading(
        plate=parse_plate(winner) if winner else None,
        detection=None,
        votes=dict(tally),
        segmented=False,
    )


def read_detection(backend: OCRBackend, detection: Detection) -> PlateReading:
    """Read one detected plate, preferring the segmented path."""
    reading = _read_segmented(backend, detection.crop)
    if reading is None or reading.plate is None:
        fallback = _read_whole(backend, detection.crop)
        if fallback.plate is not None or reading is None:
            # Keep any field breakdown we managed to obtain, for diagnostics.
            if reading is not None:
                fallback.components = reading.components
            reading = fallback

    reading.detection = detection
    # Weight the plate's support by how sure the detector was about the box.
    reading.votes = {
        text: weight * detection.confidence for text, weight in reading.votes.items()
    }
    return reading


def read_images(
    paths,
    detector: PlateDetector | None = None,
    backend: OCRBackend | None = None,
    progress=None,
) -> RunResult:
    """Run the full pipeline over one or more images and vote across them.

    ``progress`` is an optional ``callable(str)`` used to report activity; the
    CLI prints it and the GUI appends it to its log.
    """
    detector = detector or PlateDetector()
    backend = backend or get_backend()

    def report(message: str) -> None:
        if progress:
            progress(message)

    result = RunResult()
    combined: dict[str, float] = defaultdict(float)

    for path in paths:
        path = Path(path)
        report(f"Detecting plates in {path.name}...")

        image_result = ImageResult(path=path)
        detections = detector.detect(path)
        if not detections:
            report(f"  no plate found in {path.name}")
            result.images.append(image_result)
            continue

        for index, detection in enumerate(detections, start=1):
            reading = read_detection(backend, detection)
            image_result.readings.append(reading)

            how = "fields" if reading.segmented else "whole plate"
            report(
                f"  plate {index}: {reading.text} "
                f"[{how}, detector {detection.confidence:.2f}]"
            )
            for text, weight in reading.votes.items():
                combined[text] += weight

        result.images.append(image_result)

    result.votes = dict(combined)
    if combined:
        winner = max(combined, key=combined.get)
        result.plate = parse_plate(winner)

    return result
