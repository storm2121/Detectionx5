"""Detect plates, read them field by field, and vote on the answer.

The preferred path splits a plate into its three printed fields and reads each with an
alphabet restricted to what that field can contain: digits for the number and region
code, the six legal letters for the middle glyph. Every field is read from several
thresholdings of the same pixels and the results are pooled, because different
treatments fail on different plates.

If the printed separator bars cannot be located the plate is read whole, which is less
accurate but still often correct.

Passing several photographs of one vehicle strengthens the result: agreement between
independent images is much better evidence than one confident read.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Protocol

from .detector import Detection, PlateDetector
from .fusion import FusedRead, fuse, probabilistic_fusion, quality_weight
from .grammar import LETTERS, STANDARD, Plate
from .hypotheses import ViewRead, normalised
from .imaging import Image
from .normalize import normalize_text, parse_plate
from .ocr import OCRBackend, Reading, get_backend
from .preprocess import build_field_variants, build_variants
from .segment import prepare_for_ocr, segment_fields

# Field lengths come from the grammar, the single definition of plate formats.
MAX_MAIN_DIGITS = STANDARD.field("digits").max_len
MAX_REGION_DIGITS = STANDARD.field("region").max_len

Progress = Callable[[str], object]


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
    """The outcome of reading one or more images.

    ``votes`` always holds the legacy tally (the old API's confidence is computed from it);
    ``fused`` holds the result of the selected fusion method.
    """

    images: list[ImageResult] = dataclass_field(default_factory=list)
    plate: Plate | None = None
    votes: dict[str, float] = dataclass_field(default_factory=dict)
    fusion: str = "probabilistic"
    fused: FusedRead | None = None

    @property
    def text(self) -> str:
        return self.plate.text if self.plate else "unreadable"

    @property
    def agreement(self) -> int:
        """How many images independently produced the winning plate."""
        if not self.plate:
            return 0
        winner = self.plate.text
        return sum(
            1
            for image in self.images
            if image.best and image.best.plate and image.best.plate.text == winner
        )


def _argmax(tally: dict[str, float]) -> str:
    # ``max`` keeps the first of equal keys in insertion order, as the vote always has.
    return max(tally, key=lambda key: tally[key])


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
    winner = _argmax(tally)
    return winner, tally[winner]


def _vote_letter(readings: list[Reading]) -> tuple[str | None, float]:
    """Vote per character, since the engine often emits stray marks alongside."""
    tally: dict[str, float] = defaultdict(float)
    for reading in readings:
        for char in normalize_text(reading.text):
            if char in LETTERS:
                tally[char] += max(reading.confidence, 0.01)
    if not tally:
        return None, 0.0
    winner = _argmax(tally)
    return winner, tally[winner]


# --- reading strategies ----------------------------------------------------
def _read_segmented(backend: OCRBackend, detection: Detection) -> PlateReading | None:
    """Read a plate by its three fields. Returns ``None`` if not segmentable."""
    fields = segment_fields(detection.crop)
    if fields is None or not fields.is_complete:
        return None

    digit_readings: list[Reading] = []
    letter_readings: list[Reading] = []
    region_readings: list[Reading] = []

    readers: list[tuple[Image | None, list[Reading], Callable[[Image], list[Reading]], bool]] = [
        (fields.digits, digit_readings, backend.read_digits, False),
        (fields.letter, letter_readings, backend.read_letters, True),
        (fields.region, region_readings, backend.read_digits, False),
    ]
    # Only the letter field is cropped to its ink; see prepare_for_ocr.
    for source, sink, reader, tighten_first in readers:
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
        return PlateReading(plate=None, detection=detection, components=components, segmented=True)

    plate = Plate.from_tokens(f"{digits}-{letter}-{region}")
    score = digit_score + letter_score + region_score
    return PlateReading(
        plate=plate,
        detection=detection,
        votes={plate.text: score} if plate else {},
        components=components,
        segmented=True,
    )


def _read_whole(backend: OCRBackend, detection: Detection) -> PlateReading:
    """Read the plate as a single line: the fallback path."""
    tally: dict[str, float] = defaultdict(float)
    for _, variant in build_variants(detection.crop):
        for restrict in (True, False):
            for reading in backend.read(variant, restrict=restrict):
                parsed = parse_plate(reading.text)
                if parsed is not None:
                    tally[parsed.text] += max(reading.confidence, 0.01)

    winner = _argmax(tally) if tally else None
    return PlateReading(
        plate=parse_plate(winner) if winner else None,
        detection=detection,
        votes=dict(tally),
        segmented=False,
    )


def read_detection(backend: OCRBackend, detection: Detection) -> PlateReading:
    """Read one detected plate, preferring the segmented path."""
    reading = _read_segmented(backend, detection)
    if reading is None or reading.plate is None:
        fallback = _read_whole(backend, detection)
        if fallback.plate is not None or reading is None:
            # Keep any field breakdown we managed to obtain, for diagnostics.
            if reading is not None:
                fallback.components = reading.components
            reading = fallback

    # Weight the plate's support by how sure the detector was about the box.
    reading.votes = {text: weight * detection.confidence for text, weight in reading.votes.items()}
    return reading


def reading_view(reading: PlateReading) -> ViewRead:
    """One detection's EasyOCR reading as a fusion view: normalised vote shares."""
    scores: dict[str, float] = {}
    for text, weight in reading.votes.items():
        plate = parse_plate(text)
        if plate is not None:
            scores[plate.tokens] = scores.get(plate.tokens, 0.0) + weight
    return ViewRead(
        hypotheses=normalised(scores),
        prediction=reading.plate.tokens if reading.plate else None,
        votes=tuple(reading.votes.items()),
    )


def read_images(
    paths: Iterable[str | Path],
    detector: PlateDetector | None = None,
    backend: OCRBackend | None = None,
    progress: Progress | None = None,
    fusion: str = "auto",
) -> RunResult:
    """Run the full pipeline over one or more images and combine the reads across them.

    ``fusion`` is ``"probabilistic"`` (every detection's reading is a view weighted by
    detector confidence, see :mod:`plate_reader.fusion`), ``"vote"`` (the original weighted
    vote) or ``"auto"`` (the default: probabilistic when every view is calibrated, otherwise
    the vote, which for EasyOCR's uncalibrated vote shares measures better; ADR 0009).
    ``progress`` is an optional ``callable(str)`` used to report activity; the CLI prints
    it and the GUI appends it to its log.
    """
    if fusion not in ("auto", "probabilistic", "vote"):
        raise ValueError(f"unknown fusion {fusion!r}; use 'auto', 'probabilistic' or 'vote'")
    detector = detector or PlateDetector()
    backend = backend or get_backend()

    def report(message: str) -> None:
        if progress:
            progress(message)

    result = RunResult(fusion=fusion)
    combined: dict[str, float] = defaultdict(float)
    views: list[ViewRead] = []
    weights: list[float] = []

    for raw_path in paths:
        path = Path(raw_path)
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
            report(f"  plate {index}: {reading.text} [{how}, detector {detection.confidence:.2f}]")
            for text, weight in reading.votes.items():
                combined[text] += weight
            views.append(reading_view(reading))
            weights.append(detection.confidence)

        result.images.append(image_result)

    result.votes = dict(combined)
    if fusion == "auto":
        calibrated = bool(views) and all(v.calibrated for v in views if v.hypotheses)
        fusion = "probabilistic" if calibrated else "vote"
        result.fusion = fusion
    if fusion == "vote":
        if combined:
            result.plate = parse_plate(_argmax(combined))
    else:
        result.fused = probabilistic_fusion(views, weights)
        if result.fused.prediction is not None:
            result.plate = Plate.from_tokens(result.fused.prediction)

    return result


# --- the platform pipeline ------------------------------------------------------------
class ViewRecognizer(Protocol):
    """What :class:`PlatePipeline` needs from a recogniser (the CRNN runtime, or a fake)."""

    name: str

    @property
    def version(self) -> str: ...

    @property
    def conformal_threshold(self) -> float | None: ...

    def read(self, image: Image) -> ViewRead: ...


class ImageDetector(Protocol):
    def detect_image(self, image: Image) -> list[Detection]: ...


Tracer = Callable[[str], AbstractContextManager[object]]


def _no_trace(_: str) -> AbstractContextManager[object]:
    return nullcontext()


@dataclass
class ViewOutcome:
    index: int
    detection: Detection | None
    read: ViewRead | None
    weight: float
    other_detections: int = 0


@dataclass
class PipelineResult:
    views: list[ViewOutcome]
    fused: FusedRead
    plate: Plate | None
    model_version: str
    latency_ms: float
    stage_ms: dict[str, float] = dataclass_field(default_factory=dict)


class PlatePipeline:
    """Detect, read every view, fuse, and attach the conformal set (ARCHITECTURE §4).

    One photo contributes one view: its most confident detection (a second plate in a
    photo is usually another car, so it is reported, not fused). Without a detector, or
    with ``detect=False``, each photo is read as a plate crop. Views are fused
    probabilistically with unit weights by default (``fusion="legacy_vote"`` selects the
    original vote); unit weights keep a single view's calibrated posterior intact, while
    ``weighting="quality"`` tempers each view by sharpness and detector confidence.
    """

    def __init__(
        self,
        recognizer: ViewRecognizer,
        detector: ImageDetector | None = None,
        fusion: str = "probabilistic",
        weighting: str = "uniform",
        tracer: Tracer = _no_trace,
    ) -> None:
        if weighting not in ("uniform", "quality"):
            raise ValueError("weighting must be 'uniform' or 'quality'")
        self.recognizer = recognizer
        self.detector = detector
        self.fusion = fusion
        self.weighting = weighting
        self.tracer = tracer

    @property
    def model_version(self) -> str:
        return self.recognizer.version

    def _weight(self, detection: Detection) -> float:
        if self.weighting == "quality":
            from .synthetic.augment import sharpness

            return quality_weight(sharpness(detection.crop), detection.confidence)
        return 1.0

    def _read_view(
        self, index: int, detections: list[Detection], timings: dict[str, float]
    ) -> ViewOutcome:
        if not detections:
            return ViewOutcome(index=index, detection=None, read=None, weight=0.0)
        best = max(detections, key=lambda d: d.confidence)
        start = time.perf_counter()
        with self.tracer("recognise"):
            read = self.recognizer.read(best.crop)
        timings["recognise"] = timings.get("recognise", 0.0) + (time.perf_counter() - start) * 1000
        return ViewOutcome(
            index=index,
            detection=best,
            read=read,
            weight=self._weight(best),
            other_detections=len(detections) - 1,
        )

    def _finish(
        self, views: list[ViewOutcome], timings: dict[str, float], start: float
    ) -> PipelineResult:
        readable = [v for v in views if v.read is not None]
        tick = time.perf_counter()
        # Fused sets use the threshold calibrated for this number of views when the
        # recogniser has one (per-view-count calibration), else the single-view threshold.
        # A view that proposed no plate contributes nothing to the fused posterior, so only
        # the views that did are counted.
        proposing = sum(1 for v in readable if v.read is not None and v.read.hypotheses)
        threshold_for = getattr(self.recognizer, "conformal_threshold_for", None)
        threshold = (
            threshold_for(proposing)
            if callable(threshold_for)
            else self.recognizer.conformal_threshold
        )
        with self.tracer("fuse"):
            fused = fuse(
                [v.read for v in readable if v.read is not None],
                self.fusion,
                [v.weight for v in readable],
                threshold,
            )
        timings["fuse"] = (time.perf_counter() - tick) * 1000
        return PipelineResult(
            views=views,
            fused=fused,
            plate=Plate.from_tokens(fused.prediction) if fused.prediction else None,
            model_version=self.model_version,
            latency_ms=(time.perf_counter() - start) * 1000,
            stage_ms={k: round(v, 3) for k, v in timings.items()},
        )

    def read(self, images: Sequence[Image], detect: bool = True) -> PipelineResult:
        """Read one plate from several photos of one car."""
        start = time.perf_counter()
        timings: dict[str, float] = {}
        views = []
        for index, image in enumerate(images):
            tick = time.perf_counter()
            with self.tracer("detect"):
                if detect and self.detector is not None:
                    detections = self.detector.detect_image(image)
                else:
                    h, w = image.shape[:2]
                    detections = [Detection((0, 0, w, h), 1.0, image)]
            timings["detect"] = timings.get("detect", 0.0) + (time.perf_counter() - tick) * 1000
            views.append(self._read_view(index, detections, timings))
        return self._finish(views, timings, start)

    def read_detections(self, detections: Sequence[Detection]) -> PipelineResult:
        """Fuse already-detected crops, one view each (a video track)."""
        start = time.perf_counter()
        timings: dict[str, float] = {}
        views = [self._read_view(i, [d], timings) for i, d in enumerate(detections)]
        return self._finish(views, timings, start)


__all__ = [
    "ImageDetector",
    "ImageResult",
    "PipelineResult",
    "PlatePipeline",
    "PlateReading",
    "RunResult",
    "Tracer",
    "ViewOutcome",
    "ViewRecognizer",
    "read_detection",
    "read_images",
    "reading_view",
]
