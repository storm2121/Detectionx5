"""CRNN inference through ONNX Runtime, with calibrated confidence and conformal sets.

This is the torch-free path the service and the evaluation harness use (ADR 0007). The
metadata JSON next to the ONNX file carries everything post-processing needs: the charset
fingerprint, the input contract, the fitted temperature, the beam width and the conformal
thresholds per miscoverage level. A model whose charset fingerprint differs from the
grammar's is refused rather than silently mis-decoded.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

from ..grammar import GRAMMAR
from ..hypotheses import Hypothesis, ViewRead
from ..imaging import Image
from .calibrate import posterior
from .charset import CHARSET_ID, CLASSES
from .conformal import prediction_set
from .decode import DEFAULT_BEAM, greedy, log_softmax, prefix_beam_search
from .preprocess import INPUT_HEIGHT, INPUT_WIDTH, MEAN, STD, batch

Decoder = Literal["greedy", "beam", "unconstrained"]
FloatArray = npt.NDArray[np.float64]


def file_version(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


@dataclass
class CRNNMetadata:
    version: str
    charset: list[str] = field(default_factory=lambda: list(CLASSES))
    charset_id: str = CHARSET_ID
    input: dict[str, Any] = field(
        default_factory=lambda: {
            "height": INPUT_HEIGHT,
            "width": INPUT_WIDTH,
            "channels": 1,
            "mean": MEAN,
            "std": STD,
        }
    )
    temperature: float = 1.0
    calibrated: bool = False
    beam_width: int = DEFAULT_BEAM
    conformal: dict[str, float] = field(default_factory=dict)  # str(alpha) -> threshold
    #: str(views) -> str(alpha) -> threshold for fused posteriors (calibrated per view count).
    conformal_fused: dict[str, dict[str, float]] = field(default_factory=dict)
    training: dict[str, Any] = field(default_factory=dict)
    set_kind: str = "synthetic"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> Path:
        path.write_text(
            json.dumps(self.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return path

    @classmethod
    def load(cls, path: Path) -> CRNNMetadata:
        return cls(**json.loads(path.read_text(encoding="utf-8")))


def metadata_path_for(onnx_path: Path) -> Path:
    return onnx_path.with_suffix(".json")


class CRNNRuntime:
    def __init__(
        self,
        onnx_path: Path,
        metadata: CRNNMetadata | None = None,
        providers: Sequence[str] | None = None,
    ) -> None:
        import onnxruntime as ort

        self.onnx_path = onnx_path
        meta_path = metadata_path_for(onnx_path)
        if metadata is None:
            metadata = (
                CRNNMetadata.load(meta_path)
                if meta_path.exists()
                else CRNNMetadata(version=file_version(onnx_path))
            )
        if metadata.charset_id != CHARSET_ID:
            raise ValueError(
                f"{onnx_path} was trained for charset {metadata.charset_id}, the grammar has {CHARSET_ID}"
            )
        self.metadata = metadata
        options = ort.SessionOptions()
        options.log_severity_level = 3
        self.session = ort.InferenceSession(
            str(onnx_path), options, providers=list(providers or ["CPUExecutionProvider"])
        )
        self.input_name = self.session.get_inputs()[0].name

    @property
    def version(self) -> str:
        return self.metadata.version

    def logits(self, images: Sequence[Image]) -> npt.NDArray[np.float32]:
        if not images:
            return np.zeros((0, 0, len(CLASSES)), dtype=np.float32)
        inputs = batch(list(images), self.metadata.input["height"], self.metadata.input["width"])
        out = self.session.run(None, {self.input_name: inputs})[0]
        return np.asarray(out, dtype=np.float32)

    def decode(
        self,
        logits: npt.NDArray[np.float32],
        decoder: Decoder = "beam",
        alpha: float | None = 0.1,
        temperature: float | None = None,
    ) -> ViewRead:
        """Post-process one image's ``(T, C)`` logits into a :class:`ViewRead`."""
        t = self.metadata.temperature if temperature is None else temperature
        log_probs = log_softmax(logits, t)
        if decoder == "greedy":
            tokens, path_logp = greedy(log_probs)
            valid = GRAMMAR.accepts(tokens)
            return ViewRead(
                hypotheses=(Hypothesis(tokens, path_logp),) if valid else (),
                prediction=tokens or None,
                confidence=math.exp(path_logp),
                calibrated=False,
                extra={"decoder": "greedy", "grammar_valid": valid},
            )
        grammar = GRAMMAR if decoder == "beam" else None
        beam = prefix_beam_search(log_probs, self.metadata.beam_width, grammar)
        if decoder == "unconstrained":
            valid_hyps = tuple(h for h in beam if GRAMMAR.accepts(h.tokens))
            top = beam[0].tokens if beam else None
            dist = posterior(beam)
            return ViewRead(
                hypotheses=valid_hyps,
                prediction=top,
                confidence=dist[0][1] if dist else None,
                calibrated=False,
                extra={
                    "decoder": "unconstrained",
                    "grammar_valid": bool(top and GRAMMAR.accepts(top)),
                },
            )
        dist = posterior(beam)
        members: tuple[str, ...] | None = None
        covers_everything = False
        threshold = self.metadata.conformal.get(str(alpha)) if alpha is not None else None
        if threshold is not None:
            pset = prediction_set(beam, threshold)
            members, covers_everything = pset.members, pset.covers_everything
        return ViewRead(
            hypotheses=tuple(Hypothesis(tok, math.log(p)) for tok, p in dist if p > 0),
            prediction=dist[0][0] if dist else None,
            confidence=dist[0][1] if dist else None,
            prediction_set=members,
            calibrated=self.metadata.calibrated,
            extra={"decoder": "beam", "alpha": alpha, "covers_everything": covers_everything},
        )

    def read(self, image: Image, decoder: Decoder = "beam", alpha: float | None = 0.1) -> ViewRead:
        start = time.perf_counter()
        logits = self.logits([image])[0]
        read = self.decode(logits, decoder, alpha)
        latency = (time.perf_counter() - start) * 1000.0
        return ViewRead(
            hypotheses=read.hypotheses,
            prediction=read.prediction,
            confidence=read.confidence,
            prediction_set=read.prediction_set,
            latency_ms=latency,
            calibrated=read.calibrated,
            extra=read.extra,
        )


__all__ = ["CRNNMetadata", "CRNNRuntime", "Decoder", "file_version", "metadata_path_for"]
