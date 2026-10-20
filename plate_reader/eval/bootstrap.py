"""Bootstrap confidence intervals by image, by multi-view set, or by group of images.

One resample matrix is drawn per evaluated population and reused for every metric and every
recogniser, so intervals are paired: the difference between two recognisers on the same
resample is a valid paired comparison. Intervals are percentile intervals; they are honest
for the bounded, roughly smooth statistics reported here and need no normality assumption.

When units are not independent (copies of one photo, several photos of one vehicle), the
bootstrap draws whole groups: a cluster bootstrap, whose intervals reflect how many groups
there are rather than how many images (ADR 0013).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
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
    """Percentile bootstrap over a fixed population of ``n`` units.

    With ``groups`` (one label per unit), each resample draws as many groups as there are,
    with replacement, and takes every unit of each drawn group: ``weights[r, i]`` is how
    often unit ``i`` is in resample ``r``. Without groups every unit is its own group and
    the original index draw is kept, so ungrouped results do not change.
    """

    def __init__(
        self,
        n: int,
        resamples: int = DEFAULT_RESAMPLES,
        confidence: float = DEFAULT_CONFIDENCE,
        seed: int = 0,
        groups: Sequence[object] | None = None,
    ) -> None:
        if n <= 0:
            raise ValueError("bootstrap needs at least one unit")
        self.n = n
        self.resamples = resamples
        self.confidence = confidence
        self.seed = seed
        rng = np.random.default_rng(seed)
        self.weights: npt.NDArray[np.int64] | None = None
        self.n_groups = n
        if groups is None:
            self.indices = rng.integers(0, n, size=(resamples, n))
            return
        if len(groups) != n:
            raise ValueError("one group label per unit")
        _, inverse = np.unique(np.asarray([str(g) for g in groups]), return_inverse=True)
        self.n_groups = int(inverse.max()) + 1
        drawn = rng.integers(0, self.n_groups, size=(resamples, self.n_groups))
        counts = np.zeros((resamples, self.n_groups), dtype=np.int64)
        np.add.at(counts, (np.arange(resamples)[:, None], drawn), 1)
        self.weights = counts[:, inverse]
        self.indices = np.empty((0, 0), dtype=np.int64)

    @property
    def grouped(self) -> bool:
        return self.weights is not None

    def _resample_indices(self, r: int) -> npt.NDArray[np.int64]:
        if self.weights is None:
            row: npt.NDArray[np.int64] = self.indices[r]
            return row
        return np.repeat(np.arange(self.n), self.weights[r])

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
        if self.weights is None:
            sums = filled[self.indices].sum(axis=1)
            counts = valid[self.indices].sum(axis=1)
        else:
            sums = self.weights @ filled
            counts = self.weights @ valid.astype(np.int64)
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
        if self.weights is None:
            nums, dens = num[self.indices].sum(axis=1), den[self.indices].sum(axis=1)
        else:
            nums, dens = self.weights @ num, self.weights @ den
        with np.errstate(invalid="ignore", divide="ignore"):
            stats = np.where(dens > 0, nums / np.maximum(dens, 1e-12), np.nan)
        low, high = self._interval(stats)
        return Estimate(value, low, high, self.n)

    def statistic(self, fn: Callable[[npt.NDArray[np.int64]], float]) -> Estimate:
        """Any statistic of a resample, given as a function of the resampled unit indices."""
        value = fn(np.arange(self.n))
        stats = np.array(
            [fn(self._resample_indices(r)) for r in range(self.resamples)], dtype=np.float64
        )
        low, high = self._interval(stats)
        return Estimate(float(value), low, high, self.n)

    def describe(self, unit: str) -> dict[str, Any]:
        described: dict[str, Any] = {
            "resamples": self.resamples,
            "confidence": self.confidence,
            "seed": self.seed,
            "unit": "group" if self.grouped else unit,
            "method": "percentile",
        }
        if self.grouped:
            described["groups"] = self.n_groups
            described["grouped_units"] = unit
        return described


__all__ = ["DEFAULT_CONFIDENCE", "DEFAULT_RESAMPLES", "Bootstrap", "Estimate"]
