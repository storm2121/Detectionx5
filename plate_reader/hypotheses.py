"""What a recogniser says about one image: hypotheses, a prediction and its confidence.

Every recogniser (the EasyOCR baseline, the CRNN decoders) returns a :class:`ViewRead`,
which is what the evaluation harness scores, what fusion combines across photos and what
the service returns per view. Hypotheses are grammar-valid canonical token strings with
log-probabilities; for the heuristic EasyOCR path the "log-probability" is the log of the
normalised vote share, and :attr:`ViewRead.calibrated` stays ``False``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Hypothesis:
    tokens: str
    logp: float

    @property
    def probability(self) -> float:
        return math.exp(self.logp)


@dataclass(frozen=True)
class ViewRead:
    hypotheses: tuple[Hypothesis, ...] = ()
    prediction: str | None = None
    confidence: float | None = None
    prediction_set: tuple[str, ...] | None = None
    #: Raw legacy vote weights (display text, weight); only the EasyOCR path fills this.
    votes: tuple[tuple[str, float], ...] = ()
    latency_ms: float = 0.0
    calibrated: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def top(self) -> Hypothesis | None:
        return self.hypotheses[0] if self.hypotheses else None


def normalised(scores: dict[str, float]) -> tuple[Hypothesis, ...]:
    """Hypotheses from non-negative scores, as log shares, best first (ties by text)."""
    total = sum(v for v in scores.values() if v > 0)
    if total <= 0:
        return ()
    items = sorted(((t, v) for t, v in scores.items() if v > 0), key=lambda kv: (-kv[1], kv[0]))
    return tuple(Hypothesis(t, math.log(v / total)) for t, v in items)


__all__ = ["Hypothesis", "ViewRead", "normalised"]
