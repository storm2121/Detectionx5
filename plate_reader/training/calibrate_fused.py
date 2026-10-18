"""Conformal thresholds for fused reads, one per number of views (K = 1, 3, 5).

A single-view threshold is calibrated on single crops; applied to a fused posterior over K
views it has no guarantee. This step fits a threshold for each K on synthetic multi-view
calibration sets (fusing the first K views exactly as the service does), then measures the
coverage of fused sets on the separate multi-view evaluation sets with a bootstrap over both.
Real multi-photo data will have to redo these thresholds: they hold only for images
exchangeable with the synthetic sets.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final

from ..crnn.conformal import evaluate_coverage, nonconformity, quantile
from ..crnn.runtime import CRNNRuntime
from ..docs_render import SYNTHETIC_LABEL
from ..fusion import probabilistic_fusion
from ..hypotheses import Hypothesis, ViewRead
from ..synthetic.generate import GENERATOR_VERSION, make_views
from ..synthetic.splits import SPLIT_SEEDS
from .export_onnx import write_metadata

KS: Final = (1, 3, 5)
ALPHAS: Final = (0.1, 0.05)
Log = Callable[[str], object]


def _reads(
    runtime: CRNNRuntime, seed: int, n_sets: int, k: int
) -> tuple[list[list[ViewRead]], list[str]]:
    sets: list[list[ViewRead]] = []
    truths: list[str] = []
    for index in range(n_sets):
        views = make_views(seed, index, k)
        logits = runtime.logits([v.image for v in views])
        sets.append([runtime.decode(item, "beam", alpha=None) for item in logits])
        truths.append(views[0].tokens)
    return sets, truths


def _fused_hypotheses(views: Sequence[ViewRead]) -> tuple[Hypothesis, ...]:
    fused = probabilistic_fusion(list(views))
    return tuple(Hypothesis(tokens, math.log(p)) for tokens, p in fused.posterior if p > 0)


def calibrate_fused(
    onnx_path: Path,
    n_calibration: int = 1000,
    ks: Sequence[int] = KS,
    alphas: Sequence[float] = ALPHAS,
    n_test: int = 200,
    resamples: int = 1000,
    seed: int = 0,
    log: Log = print,
) -> dict[str, Any]:
    runtime = CRNNRuntime(onnx_path)
    k_max = max(ks)
    log(f"multi-view calibration split: {n_calibration} sets of {k_max} views")
    cal_sets, cal_truths = _reads(runtime, SPLIT_SEEDS["views_calibration"], n_calibration, k_max)
    log(f"multi-view test split: {n_test} sets of {k_max} views")
    test_sets, test_truths = _reads(runtime, SPLIT_SEEDS["views"], n_test, k_max)

    thresholds: dict[str, dict[str, float]] = {}
    coverage: dict[str, dict[str, Any]] = {}
    for k in ks:
        cal_beams = [_fused_hypotheses(views[:k]) for views in cal_sets]
        scores = [nonconformity(b, t) for b, t in zip(cal_beams, cal_truths, strict=True)]
        test_beams = [_fused_hypotheses(views[:k]) for views in test_sets]
        thresholds[str(k)] = {str(a): quantile(scores, a) for a in alphas}
        coverage[str(k)] = {
            str(a): evaluate_coverage(
                scores, test_beams, test_truths, a, resamples, 0.95, seed
            ).as_dict()
            for a in alphas
        }

    metadata = runtime.metadata
    metadata.conformal_fused = thresholds
    metadata = write_metadata(onnx_path, metadata)
    return {
        "schema": "detectionx5.calibration_fused/1",
        "label": SYNTHETIC_LABEL,
        "model_version": metadata.version,
        "generator_version": GENERATOR_VERSION,
        "set": {"kind": "synthetic", "name": "multi-view calibration and test sets"},
        "splits": {
            "calibration": {"seed": SPLIT_SEEDS["views_calibration"], "n_sets": n_calibration},
            "test": {"seed": SPLIT_SEEDS["views"], "n_sets": n_test},
        },
        "views": list(ks),
        "fusion": "probabilistic, unit weights",
        "thresholds": thresholds,
        "coverage": coverage,
        "note": "synthetic thresholds; real multi-photo data must refit them",
    }


__all__ = ["ALPHAS", "KS", "calibrate_fused"]
