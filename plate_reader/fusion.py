"""Combining several views (photos) of one plate.

This module starts with the legacy weighted vote, kept as the baseline the harness
reports against. Probabilistic fusion in log-probability space under the grammar
(ARCHITECTURE §8, ADR 0004) is added beside it in milestone M3.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from .grammar import Plate
from .hypotheses import ViewRead
from .normalize import parse_plate


@dataclass(frozen=True)
class FusedRead:
    prediction: str | None
    confidence: float
    method: str
    posterior: tuple[tuple[str, float], ...] = ()
    agreeing_views: int = 0
    extra: dict[str, object] = field(default_factory=dict)


def _view_votes(view: ViewRead) -> list[tuple[str, float]]:
    """The legacy vote's input: raw EasyOCR votes, or one vote of weight = confidence."""
    if view.votes:
        return list(view.votes)
    if view.prediction is None:
        return []
    plate = Plate.from_tokens(view.prediction)
    text = plate.text if plate else view.prediction
    return [(text, float(view.confidence) if view.confidence is not None else 1.0)]


def legacy_vote(views: Sequence[ViewRead], weights: Sequence[float] | None = None) -> FusedRead:
    """Sum each view's (weighted) votes per string; the winner's share is the "confidence".

    This reproduces ``pipeline.read_images``: votes are summed in view order, the first
    maximum wins, and the share of the winner is what the old API called confidence; it
    is a relative support, not a probability.
    """
    tally: dict[str, float] = defaultdict(float)
    for index, view in enumerate(views):
        w = 1.0 if weights is None else float(weights[index])
        for text, weight in _view_votes(view):
            tally[text] += weight * w
    if not tally:
        return FusedRead(prediction=None, confidence=0.0, method="legacy_vote")
    winner_text = max(tally, key=lambda key: tally[key])
    plate = parse_plate(winner_text)
    total = sum(tally.values())
    share = tally[winner_text] / total if total > 0 else 0.0
    prediction = plate.tokens if plate else None
    posterior = tuple(
        sorted(
            ((p.tokens, v / total) for t, v in tally.items() if (p := parse_plate(t))),
            key=lambda kv: -kv[1],
        )
    )
    agreeing = sum(1 for v in views if v.prediction is not None and v.prediction == prediction)
    return FusedRead(
        prediction=prediction,
        confidence=share if prediction else 0.0,
        method="legacy_vote",
        posterior=posterior,
        agreeing_views=agreeing,
    )


__all__ = ["FusedRead", "legacy_vote"]
