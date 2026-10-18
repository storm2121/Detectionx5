"""The original segmentation-and-vote path on synthetic crops, with a scripted OCR backend."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from plate_reader import pipeline
from plate_reader.detector import Detection
from plate_reader.eval.recognizers import EasyOCRRecognizer
from plate_reader.imaging import Image
from plate_reader.ocr import Reading
from plate_reader.preprocess import build_field_variants, build_variants
from plate_reader.segment import prepare_for_ocr, segment_fields, tighten
from plate_reader.synthetic import make_crop


class ScriptedBackend:
    """Returns fixed readings, so the test exercises segmentation, variants and voting."""

    name = "scripted"

    def __init__(self, whole: list[Reading] | None = None) -> None:
        self.calls: Counter[str] = Counter()
        self.whole = whole if whole is not None else [Reading("24830 ب 1", 0.5)]

    def read_digits(self, image: Image) -> list[Reading]:
        self.calls["digits"] += 1
        return [Reading("24830", 0.9), Reading("1", 0.7), Reading("O", 0.1)]

    def read_letters(self, image: Image) -> list[Reading]:
        self.calls["letters"] += 1
        return [Reading("ب", 0.8), Reading("x", 0.3)]

    def read(self, image: Image, restrict: bool = True) -> list[Reading]:
        self.calls["whole"] += 1
        return list(self.whole)

    def load_models(self) -> None:
        self.calls["load"] += 1


def _clean_crops(count: int) -> list[Image]:
    return [
        make_crop(41, i, strength=0.0, tokens="24830-ب-1", height_range=(64, 64)).image
        for i in range(count)
    ]


def test_segmentation_finds_the_bars_on_clean_synthetic_plates() -> None:
    crops = _clean_crops(10)
    complete = 0
    for crop in crops:
        fields = segment_fields(crop)
        assert fields is not None
        if fields.is_complete:
            complete += 1
            assert fields.digits is not None
            assert fields.letter is not None
            assert fields.digits.shape[1] > fields.letter.shape[1]
            assert prepare_for_ocr(fields.letter, tighten_first=True) is not None
            assert len(build_field_variants(fields.digits)) == 5
    # The old segmentation should work on most clean renders of its own plate layout.
    assert complete >= 6


def test_recogniser_reads_through_the_segmented_path() -> None:
    backend = ScriptedBackend()
    recognizer = EasyOCRRecognizer(backend=backend)
    recognizer.warmup()
    assert backend.calls["load"] == 1
    reads = [recognizer.read(crop) for crop in _clean_crops(6)]
    assert all(r.prediction == "24830-ب-1" for r in reads)
    assert any(r.extra["segmented"] for r in reads)
    assert backend.calls["digits"] > 0
    assert backend.calls["letters"] > 0
    assert all(r.confidence == pytest.approx(1.0) for r in reads)
    assert "segmentation" in recognizer.version


def test_whole_plate_fallback_when_fields_cannot_be_found() -> None:
    blank = np.full((40, 160, 3), 255, dtype=np.uint8)
    backend = ScriptedBackend()
    reading = pipeline.read_detection(backend, Detection((0, 0, 160, 40), 0.5, blank))
    assert reading.plate is not None
    assert reading.plate.text == "24830-ب-1"
    assert not reading.segmented
    assert reading.votes[reading.plate.text] == pytest.approx(
        0.5 * 0.5 * len(build_variants(blank)) * 2
    )
    nothing = ScriptedBackend(whole=[])
    unread = pipeline.read_detection(nothing, Detection((0, 0, 160, 40), 0.5, blank))
    assert unread.plate is None
    assert unread.text == "unreadable"
    assert unread.score == 0.0


def test_read_images_over_synthetic_photos(tmp_path: Path) -> None:
    crops = _clean_crops(2)

    class FakeDetector:
        def detect(self, path: Path) -> list[Detection]:
            index = int(Path(path).stem)
            if index >= len(crops):
                return []
            crop = crops[index]
            return [Detection((0, 0, crop.shape[1], crop.shape[0]), 0.8, crop)]

    paths = [tmp_path / f"{i}.png" for i in range(3)]
    messages: list[str] = []
    result = pipeline.read_images(
        paths, detector=FakeDetector(), backend=ScriptedBackend(), progress=messages.append
    )  # type: ignore[arg-type]
    assert result.text == "24830-ب-1"
    assert result.agreement == 2
    assert any("no plate found" in m for m in messages)
    assert result.images[2].best is None


def test_tighten_and_prepare_handle_degenerate_fields() -> None:
    empty = np.zeros((0, 0, 3), dtype=np.uint8)
    assert tighten(empty).size == 0
    assert prepare_for_ocr(None) is None
    assert prepare_for_ocr(np.zeros((2, 2), dtype=np.uint8)) is None
    flat = np.full((30, 20), 255, dtype=np.uint8)
    assert tighten(flat).shape == flat.shape
    grey = prepare_for_ocr(flat)
    assert grey is not None
    assert grey.ndim == 2
    assert build_variants(None) == []
    assert build_field_variants(None) == []
    assert segment_fields(None) is None
