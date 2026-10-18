"""Bootstrap confidence intervals by image (or by multi-view set).

One index matrix is drawn per evaluated population and reused for every metric and every
recogniser, so intervals are paired: the difference between two recognisers on the same
resample is a valid paired comparison. Intervals are percentile intervals; they are honest
for the bounded, roughly smooth statistics reported here and need no normality assumption.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

import numpy as np
import numpy.typing as npt

DEFAULT_RESAMPLES: Final = 1000
DEFAULT_CONFIDENCE: Final = 0.95

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class Estimate:
    value: float
    ci_low: float
    ci_high: float
    n: int

    def as_dict(self, places: int = 6) -> dict[str, Any]:
        def r(x: float) -> float | None:
            return None if np.isnan(x) else round(float(x), places)

        return {
            "value": r(self.value),
            "ci_low": r(self.ci_low),
            "ci_high": r(self.ci_high),
            "n": self.n,
        }


class Bootstrap:
    """Percentile bootstrap over a fixed population of ``n`` units."""

    def __init__(
        self,
        n: int,
        resamples: int = DEFAULT_RESAMPLES,
        confidence: float = DEFAULT_CONFIDENCE,
        seed: int = 0,
    ) -> None:
        if n <= 0:
            raise ValueError("bootstrap needs at least one unit")
        self.n = n
        self.resamples = resamples
        self.confidence = confidence
        self.seed = seed
        rng = np.random.default_rng(seed)
        self.indices = rng.integers(0, n, size=(resamples, n))

    def _interval(self, stats: FloatArray) -> tuple[float, float]:
        finite = stats[np.isfinite(stats)]
        if finite.size == 0:
            return float("nan"), float("nan")
        alpha = (1.0 - self.confidence) / 2.0
        return float(np.quantile(finite, alpha)), float(np.quantile(finite, 1.0 - alpha))

    def mean(self, values: npt.ArrayLike) -> Estimate:
        """Mean of the non-NaN values; NaN marks units a metric does not apply to."""
        x = np.asarray(values, dtype=np.float64)
        valid = ~np.isnan(x)
        count = int(valid.sum())
        if count == 0:
            return Estimate(float("nan"), float("nan"), float("nan"), 0)
        filled = np.where(valid, x, 0.0)
        sums = filled[self.indices].sum(axis=1)
        counts = valid[self.indices].sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            stats = np.where(counts > 0, sums / np.maximum(counts, 1), np.nan)
        low, high = self._interval(stats)
        return Estimate(float(filled.sum() / count), low, high, count)

    def ratio(self, numerator: npt.ArrayLike, denominator: npt.ArrayLike) -> Estimate:
        """Ratio of sums (a corpus rate such as CER), resampling numerator and denominator together."""
        num = np.asarray(numerator, dtype=np.float64)
        den = np.asarray(denominator, dtype=np.float64)
        total = float(den.sum())
        value = float(num.sum() / total) if total > 0 else float("nan")
        nums, dens = num[self.indices].sum(axis=1), den[self.indices].sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            stats = np.where(dens > 0, nums / np.maximum(dens, 1e-12), np.nan)
        low, high = self._interval(stats)
        return Estimate(value, low, high, self.n)

    def statistic(self, fn: Callable[[npt.NDArray[np.int64]], float]) -> Estimate:
        """Any statistic of a resample, given as a function of the resampled unit indices."""
        value = fn(np.arange(self.n))
        stats = np.array([fn(row) for row in self.indices], dtype=np.float64)
        low, high = self._interval(stats)
        return Estimate(float(value), low, high, self.n)

    def describe(self, unit: str) -> dict[str, Any]:
        return {
            "resamples": self.resamples,
            "confidence": self.confidence,
            "seed": self.seed,
            "unit": unit,
            "method": "percentile",
        }


__all__ = ["DEFAULT_CONFIDENCE", "DEFAULT_RESAMPLES", "Bootstrap", "Estimate"]
