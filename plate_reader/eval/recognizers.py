"""Recognisers the harness can evaluate, behind one small protocol.

A recogniser maps one plate crop (BGR) to a :class:`ViewRead`. The EasyOCR baseline wraps
the original segmentation-and-vote path unchanged, so the harness measures exactly what the
CLI, GUI and legacy API run. The CRNN recognisers (greedy, constrained beam) register here
in milestone M2.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Protocol

from ..detector import Detection
from ..hypotheses import ViewRead, normalised
from ..imaging import Image
from ..normalize import parse_plate
from ..ocr import EasyOCRBackend, OCRBackend
from ..settings import PROJECT_ROOT

if TYPE_CHECKING:
    from ..crnn.runtime import Decoder


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


class CRNNRecognizer:
    """The exported CRNN through ONNX Runtime, with one of three decoders.

    ``beam`` is the grammar-constrained prefix beam search with calibrated confidence and
    conformal sets; ``greedy`` and ``unconstrained`` are the ablations the harness compares
    it with (neither is calibrated, and either may return a string the grammar rejects).
    """

    cacheable = False
    NAMES: Final = {
        "greedy": "crnn-greedy",
        "beam": "crnn-beam",
        "unconstrained": "crnn-beam-unconstrained",
    }

    def __init__(
        self,
        decoder: Decoder = "beam",
        onnx_path: Path | None = None,
        alpha: float | None = 0.1,
        **_: object,
    ) -> None:
        from ..crnn.runtime import CRNNRuntime

        path = onnx_path or PROJECT_ROOT / "models" / "crnn.onnx"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found; run `plate train crnn` first")
        self.runtime = CRNNRuntime(path)
        self.decoder: Decoder = decoder
        self.alpha = alpha
        self.name = self.NAMES[decoder]

    @property
    def version(self) -> str:
        meta = self.runtime.metadata
        return f"crnn-{meta.version}-T{meta.temperature:g}"

    @property
    def conformal_threshold(self) -> float | None:
        """The single-view threshold at this recogniser's level (beam decoder only)."""
        if self.decoder != "beam" or self.alpha is None:
            return None
        return self.runtime.metadata.conformal.get(str(self.alpha))

    def conformal_threshold_for(self, views: int) -> float | None:
        """The threshold calibrated on fused reads of the largest calibrated view count <= ``views``.

        Falls back to the single-view threshold when no multi-view calibration exists.
        """
        if self.decoder != "beam" or self.alpha is None:
            return None
        table = self.runtime.metadata.conformal_fused
        counts = sorted(int(k) for k in table if int(k) <= max(1, views))
        if counts:
            threshold = table[str(counts[-1])].get(str(self.alpha))
            if threshold is not None:
                return threshold
        return self.conformal_threshold

    def read(self, image: Image) -> ViewRead:
        return self.runtime.read(image, self.decoder, self.alpha)


def _crnn(decoder: Decoder) -> Callable[..., Recognizer]:
    def factory(**kwargs: Any) -> Recognizer:
        return CRNNRecognizer(decoder, **kwargs)

    return factory


RecognizerFactory = Callable[..., Recognizer]
REGISTRY: dict[str, RecognizerFactory] = {
    "easyocr": EasyOCRRecognizer,
    "crnn-greedy": _crnn("greedy"),
    "crnn-beam": _crnn("beam"),
    "crnn-beam-unconstrained": _crnn("unconstrained"),
}


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
    "CRNNRecognizer",
    "EasyOCRRecognizer",
    "Recognizer",
    "build",
    "cuda_available",
    "register",
]
