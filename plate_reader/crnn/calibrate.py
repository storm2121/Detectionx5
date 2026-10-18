"""Temperature scaling for the CRNN, fitted on the probabilities the service reports.

The reported distribution over plates is the constrained beam renormalised over its
grammar-valid strings,

    q_T(s | x) = p_T(s | x) / sum_{s' in B_T(x)} p_T(s' | x),

i.e. the model's posterior conditioned on the output being a plate, with ``p_T`` the CTC
prefix probability at temperature ``T`` and ``B_T(x)`` the beam. ``T`` is chosen to
minimise the negative log-likelihood of the true plate under ``q_T`` on a held-out split,
by golden-section search on ``log T``. Fitting on exactly the function used at inference
(rather than on per-frame CTC loss) is what makes the reported confidence calibrated.
A truth outside the beam has ``q = 0``; it contributes ``-log(floor)`` and is unaffected by
``T`` only through whether the beam recovers it.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Final

import numpy as np
import numpy.typing as npt

from ..hypotheses import Hypothesis

FLOOR: Final = 1e-6
FloatArray = npt.NDArray[np.float64]
Decoder = Callable[[FloatArray, float], tuple[Hypothesis, ...]]


def posterior(hypotheses: Sequence[Hypothesis]) -> list[tuple[str, float]]:
    """The beam renormalised over its strings, best first."""
    if not hypotheses:
        return []
    top = max(h.logp for h in hypotheses)
    weights = [math.exp(h.logp - top) for h in hypotheses]
    total = sum(weights)
    return [(h.tokens, w / total) for h, w in zip(hypotheses, weights, strict=True)]


def probability_of(hypotheses: Sequence[Hypothesis], tokens: str) -> float:
    return next((p for t, p in posterior(hypotheses) if t == tokens), 0.0)


def mean_nll(beams: Sequence[Sequence[Hypothesis]], truths: Sequence[str]) -> float:
    total = 0.0
    for beam, truth in zip(beams, truths, strict=True):
        total -= math.log(max(probability_of(beam, truth), FLOOR))
    return total / max(1, len(truths))


@dataclass(frozen=True)
class TemperatureFit:
    temperature: float
    nll_before: float
    nll_after: float
    evaluations: int
    bounds: tuple[float, float]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["bounds"] = list(self.bounds)
        return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in data.items()}


def fit_temperature(
    log_probs_at: Callable[[float], Sequence[FloatArray]],
    truths: Sequence[str],
    decoder: Callable[[FloatArray], tuple[Hypothesis, ...]],
    bounds: tuple[float, float] = (0.25, 4.0),
    tolerance: float = 0.01,
) -> TemperatureFit:
    """Golden-section search for ``T`` minimising the NLL of the truths under ``q_T``.

    ``log_probs_at(T)`` returns the per-image log-softmax of ``logits / T``; ``decoder`` is
    the constrained beam search used at inference.
    """
    cache: dict[float, float] = {}

    def objective(log_t: float) -> float:
        key = round(log_t, 10)
        if key not in cache:
            beams = [decoder(lp) for lp in log_probs_at(math.exp(log_t))]
            cache[key] = mean_nll(beams, truths)
        return cache[key]

    golden = (math.sqrt(5.0) - 1.0) / 2.0
    lo, hi = math.log(bounds[0]), math.log(bounds[1])
    x1, x2 = hi - golden * (hi - lo), lo + golden * (hi - lo)
    f1, f2 = objective(x1), objective(x2)
    while hi - lo > tolerance:
        if f1 <= f2:
            hi, x2, f2 = x2, x1, f1
            x1 = hi - golden * (hi - lo)
            f1 = objective(x1)
        else:
            lo, x1, f1 = x1, x2, f2
            x2 = lo + golden * (hi - lo)
            f2 = objective(x2)
    best = (lo + hi) / 2.0
    # Keep T = 1 unless the search found a strictly better temperature: on a flat
    # objective (no truth ever enters the beam) the search would drift to a bound.
    chosen = best if objective(best) < objective(0.0) - 1e-9 else 0.0
    return TemperatureFit(
        temperature=math.exp(chosen),
        nll_before=objective(0.0),
        nll_after=objective(chosen),
        evaluations=len(cache),
        bounds=bounds,
    )


__all__ = ["FLOOR", "TemperatureFit", "fit_temperature", "mean_nll", "posterior", "probability_of"]
