"""Combining several views (photos, or thresholding variants) of one plate.

Two methods, reported side by side by the harness:

* :func:`probabilistic_fusion` (the default, ARCHITECTURE §8, ADR 0004): candidates are the
  union of the views' grammar-valid hypotheses; each view's distribution is renormalised
  over the candidate set with a floor for strings it did not propose; the fused score of a
  candidate is the weighted sum of per-view log-probabilities and the posterior is the
  softmax of the scores. With weights of one this is the product of the per-view
  posteriors, which is Bayes' rule for conditionally independent views under a uniform
  prior over the candidates (``docs/methods/fusion.md``). Per-position character
  posteriors come from aligning every hypothesis to the winner.
* :func:`legacy_vote`: the original weighted vote, kept as the baseline.

Sums use ``math.fsum`` and ties break on the token string, so the result does not depend
on the order of the views: the permutation-invariance property is exact, not approximate.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Final

from .grammar import GRAMMAR, Plate
from .hypotheses import ViewRead
from .normalize import parse_plate
from .strings import align

#: Probability given to a candidate a view did not propose, before renormalisation.
FLOOR: Final = 1e-6
#: Character label for "the winner has a symbol here, this hypothesis has none".
GAP: Final = "∅"
#: Sharpness (variance of the Laplacian) at which an image's quality weight is one half.
SHARPNESS_HALF: Final = 300.0


@dataclass(frozen=True)
class PositionPosterior:
    """Weighted distribution over what the views' hypotheses put at one winner position."""

    index: int
    symbol: str
    distribution: tuple[tuple[str, float], ...]

    @property
    def confidence(self) -> float:
        return next((p for s, p in self.distribution if s == self.symbol), 0.0)


@dataclass(frozen=True)
class FusedRead:
    prediction: str | None
    confidence: float
    method: str
    posterior: tuple[tuple[str, float], ...] = ()
    positions: tuple[PositionPosterior, ...] = ()
    agreeing_views: int = 0
    weights: tuple[float, ...] = ()
    #: Candidates whose fused nonconformity is under the threshold (``None``: no threshold).
    prediction_set: tuple[str, ...] | None = None
    extra: dict[str, object] = field(default_factory=dict)


def quality_weight(sharpness: float, detector_confidence: float = 1.0) -> float:
    """View weight from detector confidence and a saturating image-sharpness term."""
    s = max(0.0, float(sharpness))
    return float(detector_confidence) * (s / (s + SHARPNESS_HALF))


def fused_prediction_set(
    posterior: Sequence[tuple[str, float]], threshold: float | None
) -> tuple[str, ...] | None:
    """Apply a conformal threshold to a fused posterior.

    The threshold is calibrated for single views (``plate_reader.crnn.conformal``); for
    several views it is a heuristic whose coverage the harness measures on multi-view sets.
    """
    if threshold is None:
        return None
    if threshold >= 1.0:
        return tuple(s for s, _ in posterior)
    members = []
    for i, (tokens, _) in enumerate(posterior):
        others = math.fsum(p for j, (_, p) in enumerate(posterior) if j != i)
        if others <= threshold:
            members.append(tokens)
    return tuple(members)


def _view_distribution(view: ViewRead) -> dict[str, float]:
    """Probabilities of the view's grammar-valid hypotheses (duplicates summed)."""
    dist: dict[str, float] = defaultdict(float)
    for hyp in view.hypotheses:
        if GRAMMAR.accepts(hyp.tokens):
            dist[hyp.tokens] += math.exp(hyp.logp)
    return dict(dist)


def _check_weights(views: Sequence[ViewRead], weights: Sequence[float] | None) -> list[float]:
    if weights is None:
        return [1.0] * len(views)
    if len(weights) != len(views):
        raise ValueError("one weight per view is required")
    if any(w < 0 or not math.isfinite(w) for w in weights):
        raise ValueError("weights must be finite and non-negative")
    return [float(w) for w in weights]


def probabilistic_fusion(
    views: Sequence[ViewRead],
    weights: Sequence[float] | None = None,
    threshold: float | None = None,
    floor: float = FLOOR,
) -> FusedRead:
    w = _check_weights(views, weights)
    dists = [_view_distribution(v) for v in views]
    candidates = sorted({s for d in dists for s in d})
    if not candidates:
        return FusedRead(prediction=None, confidence=0.0, method="probabilistic", weights=tuple(w))

    # Per view: renormalise over the candidate set, unseen strings at the floor.
    log_tilde: list[dict[str, float]] = []
    for dist in dists:
        if not dist:
            log_tilde.append({})  # a view with no hypothesis abstains
            continue
        raw = {s: max(dist.get(s, 0.0), floor) for s in candidates}
        log_z = math.log(math.fsum(raw.values()))
        log_tilde.append({s: math.log(p) - log_z for s, p in raw.items()})

    scores = {
        s: math.fsum(wv * lt[s] for wv, lt in zip(w, log_tilde, strict=True) if lt)
        for s in candidates
    }
    top = max(scores.values())
    unnorm = {s: math.exp(v - top) for s, v in scores.items()}
    z = math.fsum(unnorm.values())
    posterior = sorted(((s, p / z) for s, p in unnorm.items()), key=lambda kv: (-kv[1], kv[0]))
    winner, confidence = posterior[0]
    positions = per_position_posterior(winner, w, log_tilde)
    agreeing = sum(1 for d in dists if d and max(d, key=lambda s: (d[s], s)) == winner)
    return FusedRead(
        prediction=winner,
        confidence=confidence,
        method="probabilistic",
        posterior=tuple(posterior),
        positions=positions,
        agreeing_views=agreeing,
        weights=tuple(w),
        prediction_set=fused_prediction_set(posterior, threshold),
    )


def per_position_posterior(
    winner: str, weights: Sequence[float], log_tilde: Sequence[dict[str, float]]
) -> tuple[PositionPosterior, ...]:
    """Align each view's hypotheses to the winner and accumulate weighted symbol votes.

    A hypothesis votes with weight ``w_v * p_v(s)`` (its view's renormalised probability)
    for whatever it aligns to each winner position: a symbol, or :data:`GAP` where it has
    none. Insertions relative to the winner are not attributed to any position.
    """
    votes: list[dict[str, list[float]]] = [defaultdict(list) for _ in winner]
    for weight, lt in zip(weights, log_tilde, strict=True):
        for tokens, logp in lt.items():
            mass = weight * math.exp(logp)
            if mass <= 0.0:
                continue
            for i, j in align(winner, tokens):
                if i is None:
                    continue
                votes[i][tokens[j] if j is not None else GAP].append(mass)
    out = []
    for index, symbol in enumerate(winner):
        totals = {s: math.fsum(m) for s, m in votes[index].items()}
        z = math.fsum(totals.values())
        dist = (
            tuple(sorted(((s, v / z) for s, v in totals.items()), key=lambda kv: (-kv[1], kv[0])))
            if z > 0
            else ((symbol, 1.0),)
        )
        out.append(PositionPosterior(index=index, symbol=symbol, distribution=dist))
    return tuple(out)


def _view_votes(view: ViewRead) -> list[tuple[str, float]]:
    """The legacy vote's input: raw EasyOCR votes, or one vote of weight = confidence."""
    if view.votes:
        return list(view.votes)
    if view.prediction is None:
        return []
    plate = Plate.from_tokens(view.prediction)
    text = plate.text if plate else view.prediction
    return [(text, float(view.confidence) if view.confidence is not None else 1.0)]


def legacy_vote(
    views: Sequence[ViewRead],
    weights: Sequence[float] | None = None,
    threshold: float | None = None,
) -> FusedRead:
    """Sum each view's (weighted) votes per string; the winner's share is the "confidence".

    This reproduces ``pipeline.read_images``' original vote: votes are summed in view
    order, the first maximum wins, and the share of the winner is what the old API called
    confidence; it is a relative support, not a probability. ``threshold`` is accepted for
    interface symmetry and ignored, because no conformal set can be formed from a share.
    """
    w = _check_weights(views, weights)
    tally: dict[str, float] = defaultdict(float)
    for index, view in enumerate(views):
        for text, weight in _view_votes(view):
            tally[text] += weight * w[index]
    if not tally:
        return FusedRead(prediction=None, confidence=0.0, method="legacy_vote", weights=tuple(w))
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
        weights=tuple(w),
    )


Fuser = Callable[[Sequence[ViewRead], Sequence[float] | None, float | None], FusedRead]
FUSERS: Final[dict[str, Fuser]] = {
    "probabilistic": probabilistic_fusion,
    "legacy_vote": legacy_vote,
}


def fuse(
    views: Sequence[ViewRead],
    method: str = "probabilistic",
    weights: Sequence[float] | None = None,
    threshold: float | None = None,
) -> FusedRead:
    try:
        fuser = FUSERS[method]
    except KeyError:
        raise ValueError(f"unknown fusion method {method!r}; known: {', '.join(FUSERS)}") from None
    return fuser(views, weights, threshold)


__all__ = [
    "FLOOR",
    "FUSERS",
    "GAP",
    "SHARPNESS_HALF",
    "FusedRead",
    "Fuser",
    "PositionPosterior",
    "fuse",
    "fused_prediction_set",
    "legacy_vote",
    "per_position_posterior",
    "probabilistic_fusion",
    "quality_weight",
]
