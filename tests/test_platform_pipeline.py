"""PlatePipeline: detect, read every view, fuse probabilistically, attach the conformal set."""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager

import numpy as np
import pytest

from plate_reader.detector import Detection
from plate_reader.hypotheses import Hypothesis, ViewRead
from plate_reader.pipeline import PlatePipeline


class Recognizer:
    name = "fake"
    version = "fake-1"
    conformal_threshold: float | None = 0.6

    def read(self, image: np.ndarray) -> ViewRead:
        if float(image.mean()) < 100:
            hyps = (Hypothesis("12-WW", math.log(0.9)), Hypothesis("13-WW", math.log(0.1)))
        else:
            hyps = (Hypothesis("13-WW", math.log(0.6)), Hypothesis("12-WW", math.log(0.4)))
        return ViewRead(
            hypotheses=hyps,
            prediction=hyps[0].tokens,
            confidence=hyps[0].probability,
            calibrated=True,
        )


class Detector:
    def detect_image(self, image: np.ndarray) -> list[Detection]:
        if image.max() == 0:
            return []
        h, w = image.shape[:2]
        return [
            Detection((0, 0, w // 2, h), 0.5, image[:, : w // 2].copy()),
            Detection((0, 0, w, h), 0.9, image.copy()),
        ]


def photo(level: int) -> np.ndarray:
    return np.full((20, 60, 3), level, dtype=np.uint8)


def test_probabilistic_fusion_is_the_default() -> None:
    pipeline = PlatePipeline(Recognizer(), Detector())
    result = pipeline.read([photo(50), photo(50), photo(200)])
    assert pipeline.fusion == "probabilistic"
    assert result.fused.method == "probabilistic"
    assert result.plate is not None
    assert result.plate.text == "12 WW"
    # 0.9 * 0.9 * 0.4 against 0.1 * 0.1 * 0.6, renormalised.
    assert result.fused.confidence == pytest.approx(0.324 / (0.324 + 0.006))
    assert result.fused.prediction_set == ("12-WW",)
    assert [v.other_detections for v in result.views] == [1, 1, 1]
    assert all(v.detection is not None and v.detection.confidence == 0.9 for v in result.views)
    assert result.model_version == "fake-1"
    assert set(result.stage_ms) == {"detect", "recognise", "fuse"}


def test_the_legacy_vote_stays_selectable() -> None:
    pipeline = PlatePipeline(Recognizer(), Detector(), fusion="legacy_vote")
    result = pipeline.read([photo(200), photo(200), photo(50)])
    assert result.fused.method == "legacy_vote"
    assert result.fused.prediction_set is None


def test_crop_mode_abstaining_views_and_tracks() -> None:
    pipeline = PlatePipeline(Recognizer(), detector=None)
    crops = pipeline.read([photo(50)])
    assert crops.views[0].detection is not None
    assert crops.views[0].detection.box == (0, 0, 60, 20)
    with_detector = PlatePipeline(Recognizer(), Detector())
    forced = with_detector.read([photo(50)], detect=False)
    assert forced.views[0].other_detections == 0
    empty = with_detector.read([photo(0)])
    assert empty.views[0].read is None
    assert empty.plate is None
    track = with_detector.read_detections([Detection((0, 0, 60, 20), 0.8, photo(50))] * 3)
    assert len(track.views) == 3
    assert track.plate is not None


def test_quality_weighting_and_tracing() -> None:
    names: list[str] = []

    @contextmanager
    def tracer(name: str) -> Iterator[None]:
        names.append(name)
        yield

    textured = np.random.default_rng(0).integers(0, 90, size=(20, 60, 3), dtype=np.uint8)
    pipeline = PlatePipeline(Recognizer(), Detector(), weighting="quality", tracer=tracer)
    result = pipeline.read([textured])
    assert 0.0 < result.views[0].weight < 0.9
    assert names == ["detect", "recognise", "fuse"]
    with pytest.raises(ValueError):
        PlatePipeline(Recognizer(), weighting="loud")


class CountingRecognizer(Recognizer):
    """Dark crops are read; light ones propose nothing. Records the view count asked for."""

    def __init__(self) -> None:
        self.asked: list[int] = []

    def conformal_threshold_for(self, views: int) -> float:
        self.asked.append(views)
        return 0.6

    def read(self, image: np.ndarray) -> ViewRead:
        if float(image.mean()) < 100:
            return super().read(image)
        return ViewRead(hypotheses=(), prediction=None, confidence=None, calibrated=True)


def test_views_that_propose_nothing_do_not_count_towards_the_threshold() -> None:
    recognizer = CountingRecognizer()
    pipeline = PlatePipeline(recognizer, detector=None)
    result = pipeline.read([photo(50), photo(200), photo(50)])
    assert recognizer.asked == [2]
    assert result.plate is not None
    assert result.plate.text == "12 WW"
