"""The service's inference engine: the platform pipeline plus the review policy.

Detection, one view per photo, probabilistic fusion and the conformal set come from
:class:`plate_reader.pipeline.PlatePipeline` (ADR 0004, ADR 0009); the engine adds the
OpenTelemetry spans and the decision of whether a read goes to the human review queue.
It is the seam the tests replace with fakes; nothing in it touches the database.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from plate_reader.detector import Detection
from plate_reader.fusion import FusedRead
from plate_reader.imaging import Image
from plate_reader.pipeline import (
    ImageDetector,
    PipelineResult,
    PlatePipeline,
    ViewOutcome,
    ViewRecognizer,
)
from plate_reader.telemetry import stage

ReviewReason = Literal["set_size", "empty_set", "low_confidence", "unreadable"]


@dataclass
class EngineResult(PipelineResult):
    review_reason: ReviewReason | None = None


def review_reason(
    fused: FusedRead, threshold: float, any_view: bool, review_empty_sets: bool = False
) -> ReviewReason | None:
    """Queue a read when its conformal set holds more than one plate or confidence is low.

    An empty set means even the best candidate is less conforming than the calibration
    quantile; for a model far more accurate than 1 - alpha this happens to about alpha of
    all reads, so queueing them is a setting rather than the default (ADR 0004).
    """
    if fused.prediction is None:
        return "unreadable" if any_view else None
    if fused.prediction_set is not None:
        if len(fused.prediction_set) > 1:
            return "set_size"
        if not fused.prediction_set and review_empty_sets:
            return "empty_set"
    if fused.confidence < threshold:
        return "low_confidence"
    return None


class Engine(PlatePipeline):
    def __init__(
        self,
        recognizer: ViewRecognizer,
        detector: ImageDetector | None = None,
        fusion: str = "probabilistic",
        weighting: str = "uniform",
        review_threshold: float = 0.9,
        review_empty_sets: bool = False,
    ) -> None:
        super().__init__(recognizer, detector, fusion, weighting, tracer=stage)
        self.review_threshold = review_threshold
        self.review_empty_sets = review_empty_sets

    def _review(self, result: PipelineResult) -> EngineResult:
        any_view = any(v.read is not None for v in result.views)
        return EngineResult(
            views=result.views,
            fused=result.fused,
            plate=result.plate,
            model_version=result.model_version,
            latency_ms=result.latency_ms,
            stage_ms=result.stage_ms,
            review_reason=review_reason(
                result.fused, self.review_threshold, any_view, self.review_empty_sets
            ),
        )

    def read(self, images: Sequence[Image], detect: bool = True) -> EngineResult:
        return self._review(super().read(images, detect))

    def read_detections(self, detections: Sequence[Detection]) -> EngineResult:
        return self._review(super().read_detections(detections))


__all__ = [
    "Engine",
    "EngineResult",
    "ImageDetector",
    "ReviewReason",
    "ViewOutcome",
    "ViewRecognizer",
    "review_reason",
]
