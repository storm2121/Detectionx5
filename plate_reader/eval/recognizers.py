"""Recognisers the harness can evaluate, behind one small protocol.

A recogniser maps one plate crop (BGR) to a :class:`ViewRead`. The EasyOCR baseline wraps
the original segmentation-and-vote path unchanged, so the harness measures exactly what the
CLI, GUI and legacy API run. The CRNN recognisers (greedy, constrained beam) register here
in milestone M2.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from ..detector import Detection
from ..hypotheses import ViewRead, normalised
from ..imaging import Image
from ..normalize import parse_plate
from ..ocr import EasyOCRBackend, OCRBackend


class Recognizer(Protocol):
    name: str

    @property
    def version(self) -> str: ...

    def read(self, image: Image) -> ViewRead: ...


def cuda_available() -> bool:
    try:
        import torch
    except ImportError:  # pragma: no cover - the ml group is not installed
        return False
    return bool(torch.cuda.is_available())


class EasyOCRRecognizer:
    """The original pipeline on one crop: field segmentation, two EasyOCR models, a vote."""

    name = "easyocr"
    #: Reads are deterministic for a given image and slow, so the harness may cache them.
    cacheable = True

    def __init__(self, backend: OCRBackend | None = None, use_gpu: bool | None = None) -> None:
        self.backend: OCRBackend = backend or EasyOCRBackend(
            use_gpu=cuda_available() if use_gpu is None else use_gpu
        )

    @property
    def version(self) -> str:
        try:
            import easyocr

            engine = f"easyocr-{easyocr.__version__}"
        except ImportError:  # pragma: no cover - the ml group is not installed
            engine = "easyocr-unavailable"
        return f"{engine}+segmentation"

    def warmup(self) -> None:
        load = getattr(self.backend, "load_models", None)
        if callable(load):
            load()

    def read(self, image: Image) -> ViewRead:
        from .. import pipeline

        height, width = image.shape[:2]
        detection = Detection(box=(0, 0, width, height), confidence=1.0, crop=image)
        start = time.perf_counter()
        reading = pipeline.read_detection(self.backend, detection)
        latency = (time.perf_counter() - start) * 1000.0
        scores: dict[str, float] = {}
        for text, weight in reading.votes.items():
            plate = parse_plate(text)
            if plate is not None:
                scores[plate.tokens] = scores.get(plate.tokens, 0.0) + weight
        hypotheses = normalised(scores)
        prediction = reading.plate.tokens if reading.plate else None
        confidence = None
        if prediction is not None:
            confidence = next((h.probability for h in hypotheses if h.tokens == prediction), 0.0)
        return ViewRead(
            hypotheses=hypotheses,
            prediction=prediction,
            confidence=confidence,
            votes=tuple(reading.votes.items()),
            latency_ms=latency,
            calibrated=False,
            extra={"segmented": reading.segmented},
        )


RecognizerFactory = Callable[..., Recognizer]
REGISTRY: dict[str, RecognizerFactory] = {"easyocr": EasyOCRRecognizer}


def register(name: str, factory: RecognizerFactory) -> None:
    REGISTRY[name] = factory


def build(name: str, **kwargs: object) -> Recognizer:
    try:
        factory = REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"unknown recogniser {name!r}; known: {', '.join(sorted(REGISTRY))}"
        ) from None
    return factory(**kwargs)


__all__ = [
    "REGISTRY",
    "EasyOCRRecognizer",
    "Recognizer",
    "build",
    "cuda_available",
    "register",
]
