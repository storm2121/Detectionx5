"""Tests for plate segmentation.

These use the bundled sample image and the committed detector weights. They
need ultralytics and opencv but not an OCR engine, so they stay reasonably
quick; they skip rather than fail when the model or its dependencies are
missing, so the fast text tests can still run on a bare checkout.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402

SAMPLE = ROOT / "samples" / "car.jpg"

pytestmark = pytest.mark.skipif(
    not (SAMPLE.exists() and config.MODEL_PATH.exists()),
    reason="sample image or model weights not available",
)


@pytest.fixture(scope="module")
def crop():
    pytest.importorskip("ultralytics")
    from plate_reader.detector import PlateDetector

    detections = PlateDetector().detect(SAMPLE)
    assert detections, "expected at least one plate in the sample image"
    return detections[0].crop


def test_detector_deduplicates_boxes():
    """YOLOv10 emits overlapping boxes for this plate; only one should survive."""
    pytest.importorskip("ultralytics")
    from plate_reader.detector import PlateDetector

    detections = PlateDetector().detect(SAMPLE)
    assert len(detections) == 1


def test_segments_into_three_fields(crop):
    from plate_reader.segment import segment_fields

    fields = segment_fields(crop)
    assert fields is not None
    assert fields.is_complete, "the two separator bars should have been found"


def test_field_order_and_size(crop):
    """The digit block is the widest field; the letter sits between the bars."""
    from plate_reader.segment import segment_fields

    fields = segment_fields(crop)
    assert fields.digits.shape[1] > fields.letter.shape[1]
    assert fields.region.shape[1] > 0


def test_tighten_removes_border_bands(crop):
    """Cropping to the ink should shorten the letter strip noticeably."""
    from plate_reader.segment import segment_fields, tighten

    letter = segment_fields(crop).letter
    assert tighten(letter).shape[0] < letter.shape[0]


def test_isolate_plate_shrinks_the_crop(crop):
    from plate_reader.segment import isolate_plate

    assert isolate_plate(crop).shape[0] <= crop.shape[0]
