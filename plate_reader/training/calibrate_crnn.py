"""Calibrate an exported CRNN: temperature, conformal thresholds, and measured coverage.

Three disjoint synthetic splits (ADR 0004): ``calibration`` fits the temperature,
``conformal`` sets the thresholds for each miscoverage level, and ``test`` measures
coverage and set size. Logits come from the ONNX graph the service runs, and decoding is
the same constrained beam, so the numbers describe exactly what is served. Results go to
``results/calibration_crnn.json`` (labelled synthetic) and into the model's metadata.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final

import numpy as np

from ..crnn.calibrate import fit_temperature, posterior
from ..crnn.conformal import evaluate_coverage, nonconformity, quantile
from ..crnn.decode import log_softmax, prefix_beam_search
from ..crnn.runtime import CRNNRuntime
from ..docs_render import SYNTHETIC_LABEL
from ..eval.bootstrap import Bootstrap
from ..eval.metrics import ece, reliability
from ..grammar import GRAMMAR
from ..hypotheses import Hypothesis
from ..synthetic.generate import GENERATOR_VERSION, make_crop
from ..synthetic.splits import SPLIT_SEEDS
from .export_onnx import write_metadata

ALPHAS: Final = (0.1, 0.05)
Log = Callable[[str], object]


def _split(name: str, n: int) -> tuple[list[Any], list[str]]:
    samples = [make_crop(SPLIT_SEEDS[name], i) for i in range(n)]
    return [s.image for s in samples], [s.tokens for s in samples]


def _beams(logits: np.ndarray, temperature: float, width: int) -> list[tuple[Hypothesis, ...]]:
    return [prefix_beam_search(log_softmax(item, temperature), width, GRAMMAR) for item in logits]


def _calibration_metrics(
    beams: Sequence[Sequence[Hypothesis]], truths: Sequence[str], bootstrap: Bootstrap
) -> dict[str, Any]:
    conf = np.array([posterior(b)[0][1] if b else 0.0 for b in beams])
    correct = np.array(
        [float(bool(b) and b[0].tokens == t) for b, t in zip(beams, truths, strict=True)]
    )

    def ece_of(idx: np.ndarray) -> float:
        return ece(conf[idx], correct[idx])

    return {
        "exact_match": bootstrap.mean(correct).as_dict(),
        "mean_confidence": bootstrap.mean(conf).as_dict(),
        "ece": bootstrap.statistic(ece_of).as_dict(),
        "reliability": reliability(conf, correct),
    }


def calibrate(
    onnx_path: Path,
    n_calibration: int = 2000,
    n_conformal: int = 2000,
    n_test: int = 2000,
    alphas: Sequence[float] = ALPHAS,
    resamples: int = 1000,
    seed: int = 0,
    log: Log = print,
) -> dict[str, Any]:
    runtime = CRNNRuntime(onnx_path)
    width = runtime.metadata.beam_width

    log(f"calibration split: {n_calibration} crops")
    cal_images, cal_truths = _split("calibration", n_calibration)
    cal_logits = runtime.logits(cal_images)
    fit = fit_temperature(
        lambda t: [log_softmax(item, t) for item in cal_logits],
        cal_truths,
        lambda lp: prefix_beam_search(lp, width, GRAMMAR),
    )
    temperature = fit.temperature
    log(f"temperature {temperature:.4f}: NLL {fit.nll_before:.4f} -> {fit.nll_after:.4f}")
    cal_boot = Bootstrap(n_calibration, resamples, 0.95, seed)
    before = _calibration_metrics(_beams(cal_logits, 1.0, width), cal_truths, cal_boot)
    after = _calibration_metrics(_beams(cal_logits, temperature, width), cal_truths, cal_boot)

    log(f"conformal split: {n_conformal} crops")
    conf_images, conf_truths = _split("conformal", n_conformal)
    conf_beams = _beams(runtime.logits(conf_images), temperature, width)
    scores = [nonconformity(b, t) for b, t in zip(conf_beams, conf_truths, strict=True)]
    thresholds = {str(alpha): quantile(scores, alpha) for alpha in alphas}

    log(f"test split: {n_test} crops")
    test_images, test_truths = _split("test", n_test)
    test_beams = _beams(runtime.logits(test_images), temperature, width)
    coverage = {
        str(alpha): evaluate_coverage(
            scores, test_beams, test_truths, alpha, resamples, 0.95, seed
        ).as_dict()
        for alpha in alphas
    }
    test_boot = Bootstrap(n_test, resamples, 0.95, seed)
    test_metrics = _calibration_metrics(test_beams, test_truths, test_boot)

    metadata = runtime.metadata
    metadata.temperature = round(temperature, 6)
    metadata.calibrated = True
    metadata.conformal = {k: float(v) for k, v in thresholds.items()}
    metadata = write_metadata(onnx_path, metadata)

    return {
        "schema": "detectionx5.calibration/1",
        "label": SYNTHETIC_LABEL,
        "model_version": metadata.version,
        "generator_version": GENERATOR_VERSION,
        "splits": {
            "calibration": {"seed": SPLIT_SEEDS["calibration"], "n": n_calibration},
            "conformal": {"seed": SPLIT_SEEDS["conformal"], "n": n_conformal},
            "test": {"seed": SPLIT_SEEDS["test"], "n": n_test},
        },
        "set": {"kind": "synthetic", "name": "crnn calibration splits"},
        "bootstrap": cal_boot.describe("image"),
        "temperature": fit.as_dict(),
        "calibration_split": {"before": before, "after": after},
        "test_split": test_metrics,
        "conformal": {
            "thresholds": {k: float(v) for k, v in thresholds.items()},
            "coverage": coverage,
        },
        "beam_width": width,
    }


__all__ = ["ALPHAS", "calibrate"]
