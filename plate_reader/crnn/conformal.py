"""Split conformal prediction sets over plate strings.

Nonconformity of a candidate ``s`` for image ``x`` is ``1 - q(s | x)`` with ``q`` the
calibrated beam posterior (see :mod:`.calibrate`). It is computed as the summed posterior
of the *other* candidates, which equals ``1 - q`` exactly but does not round very
confident reads to an exact zero in floating point; exact ties at zero would make the
empirical quantile over-cover. A truth outside the beam scores 1.

On a calibration split of size n the threshold is the ``ceil((n + 1)(1 - alpha))``-th
smallest score (the conservative split-conformal quantile). The set for a new image is
every beam string whose score is at most the threshold; when the threshold reaches 1 the
set must contain every string, which is flagged instead of enumerated. Under
exchangeability, ``P(truth in set) >= 1 - alpha``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from ..eval.bootstrap import Bootstrap, Estimate
from ..hypotheses import Hypothesis
from .calibrate import posterior

FloatArray = npt.NDArray[np.float64]


def scores_of(hypotheses: Sequence[Hypothesis]) -> list[tuple[str, float]]:
    """``(tokens, 1 - q)`` for every beam string, computed as the mass of the others."""
    dist = posterior(hypotheses)
    out = []
    for i, (tokens, _) in enumerate(dist):
        others = math.fsum(p for j, (_, p) in enumerate(dist) if j != i)
        out.append((tokens, others))
    return out


def nonconformity(hypotheses: Sequence[Hypothesis], truth: str) -> float:
    return next((s for t, s in scores_of(hypotheses) if t == truth), 1.0)


def quantile(scores: Sequence[float] | FloatArray, alpha: float) -> float:
    """The conservative split-conformal threshold; 1.0 means "every string"."""
    values = np.sort(np.asarray(scores, dtype=np.float64))
    n = values.size
    rank = math.ceil((n + 1) * (1.0 - alpha))
    if n == 0 or rank > n:
        return 1.0
    return float(values[rank - 1])


@dataclass(frozen=True)
class PredictionSet:
    members: tuple[str, ...]
    covers_everything: bool = False

    @property
    def size(self) -> int:
        return len(self.members)


def prediction_set(hypotheses: Sequence[Hypothesis], threshold: float) -> PredictionSet:
    if threshold >= 1.0:
        return PredictionSet(tuple(h.tokens for h in hypotheses), covers_everything=True)
    return PredictionSet(tuple(t for t, s in scores_of(hypotheses) if s <= threshold))


@dataclass(frozen=True)
class CoverageReport:
    alpha: float
    threshold: float
    coverage: Estimate
    set_size: Estimate
    singleton_rate: float
    empty_rate: float
    covers_everything_rate: float
    n_calibration: int
    n_test: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "alpha": self.alpha,
            "level": round(1.0 - self.alpha, 6),
            "threshold": float(self.threshold),
            "coverage": self.coverage.as_dict(),
            "set_size": self.set_size.as_dict(),
            "singleton_rate": round(self.singleton_rate, 6),
            "empty_rate": round(self.empty_rate, 6),
            "covers_everything_rate": round(self.covers_everything_rate, 6),
            "n_calibration": self.n_calibration,
            "n_test": self.n_test,
            "interval": "joint bootstrap over calibration and test splits",
        }


def evaluate_coverage(
    calibration_scores: Sequence[float],
    test_beams: Sequence[Sequence[Hypothesis]],
    test_truths: Sequence[str],
    alpha: float,
    resamples: int = 1000,
    confidence: float = 0.95,
    seed: int = 0,
) -> CoverageReport:
    """Coverage and set size on a test split, with an interval that also resamples calibration.

    Each bootstrap replicate redraws the calibration split, recomputes the threshold, and
    redraws the test split; the interval therefore includes the threshold's own sampling
    variability, which a test-only bootstrap would ignore.
    """
    cal = np.asarray(calibration_scores, dtype=np.float64)
    test_scores = np.array(
        [nonconformity(b, t) for b, t in zip(test_beams, test_truths, strict=True)]
    )
    all_scores = [np.array([s for _, s in scores_of(b)]) for b in test_beams]
    threshold = quantile(cal, alpha)

    def sizes_at(q: float) -> FloatArray:
        if q >= 1.0:
            return np.array([float(len(s)) for s in all_scores])
        return np.array([float((s <= q).sum()) for s in all_scores])

    sizes = sizes_at(threshold)
    covered = (
        (test_scores <= threshold).astype(np.float64)
        if threshold < 1.0
        else np.ones_like(test_scores)
    )

    rng = np.random.default_rng(seed)
    cal_boot = rng.integers(0, cal.size, size=(resamples, cal.size))
    test_boot = Bootstrap(len(test_scores), resamples, confidence, seed + 1)
    coverages = np.empty(resamples)
    mean_sizes = np.empty(resamples)
    sorted_scores = [np.sort(s) for s in all_scores]
    for r in range(resamples):
        q = quantile(cal[cal_boot[r]], alpha)
        idx = test_boot.indices[r]
        if q >= 1.0:
            coverages[r] = 1.0
            mean_sizes[r] = float(np.mean([len(all_scores[i]) for i in idx]))
        else:
            coverages[r] = float((test_scores[idx] <= q).mean())
            mean_sizes[r] = float(
                np.mean([np.searchsorted(sorted_scores[i], q, side="right") for i in idx])
            )
    alpha_ci = (1.0 - confidence) / 2.0

    def estimate(value: float, stats: FloatArray) -> Estimate:
        return Estimate(
            value,
            float(np.quantile(stats, alpha_ci)),
            float(np.quantile(stats, 1 - alpha_ci)),
            len(test_scores),
        )

    return CoverageReport(
        alpha=alpha,
        threshold=threshold,
        coverage=estimate(float(covered.mean()), coverages),
        set_size=estimate(float(sizes.mean()), mean_sizes),
        singleton_rate=float((sizes == 1).mean()),
        empty_rate=float((sizes == 0).mean()),
        covers_everything_rate=1.0 if threshold >= 1.0 else 0.0,
        n_calibration=int(cal.size),
        n_test=len(test_scores),
    )


__all__ = [
    "CoverageReport",
    "PredictionSet",
    "evaluate_coverage",
    "nonconformity",
    "prediction_set",
    "quantile",
    "scores_of",
]
