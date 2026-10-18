"""Property tests for multi-view fusion (ARCHITECTURE §8)."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from plate_reader import grammar
from plate_reader.fusion import (
    GAP,
    fuse,
    legacy_vote,
    probabilistic_fusion,
    quality_weight,
)
from plate_reader.hypotheses import Hypothesis, ViewRead

POOL = ["12-WW", "13-WW", "112-WW", "24830-ب-1", "24830-د-1", "2483-ب-1", "7-ط-45", "7-ط-46"]


@st.composite
def views_and_weights(draw: st.DrawFn, min_views: int = 1) -> tuple[list[ViewRead], list[float]]:
    count = draw(st.integers(min_views, 5))
    views = []
    for _ in range(count):
        names = draw(st.lists(st.sampled_from(POOL), min_size=0, max_size=4, unique=True))
        masses = [draw(st.floats(1e-3, 1.0)) for _ in names]
        total = sum(masses)
        hyps = tuple(
            sorted(
                (Hypothesis(n, math.log(m / total)) for n, m in zip(names, masses, strict=True)),
                key=lambda h: (-h.logp, h.tokens),
            )
        )
        views.append(ViewRead(hypotheses=hyps, prediction=hyps[0].tokens if hyps else None))
    weights = [draw(st.floats(0.05, 3.0)) for _ in views]
    return views, weights


def _view_argmax(view: ViewRead) -> str:
    best = max(view.hypotheses, key=lambda h: (h.logp, [-ord(c) for c in h.tokens]))
    return best.tokens


@given(views_and_weights(), st.randoms(use_true_random=False))
def test_fusion_is_permutation_invariant(
    data: tuple[list[ViewRead], list[float]], rnd: object
) -> None:
    views, weights = data
    order = list(range(len(views)))
    rnd.shuffle(order)  # type: ignore[attr-defined]
    a = probabilistic_fusion(views, weights)
    b = probabilistic_fusion([views[i] for i in order], [weights[i] for i in order])
    assert a.prediction == b.prediction
    assert a.confidence == b.confidence
    assert a.posterior == b.posterior
    assert a.positions == b.positions
    assert a.agreeing_views == b.agreeing_views


@given(views_and_weights())
def test_single_view_fusion_returns_that_views_argmax(
    data: tuple[list[ViewRead], list[float]],
) -> None:
    views, weights = data
    view = next((v for v in views if v.hypotheses), None)
    if view is None:
        assert probabilistic_fusion(views[:1]).prediction is None
        return
    # The argmax survives any positive weight (a weight is an exponent on the evidence)...
    assert probabilistic_fusion([view], [weights[0]]).prediction == view.hypotheses[0].tokens
    # ...and with weight one the fused posterior is the view's own distribution.
    fused = probabilistic_fusion([view])
    assert fused.prediction == view.hypotheses[0].tokens
    expected = math.exp(view.hypotheses[0].logp) / math.fsum(
        math.exp(h.logp) for h in view.hypotheses
    )
    assert fused.confidence == pytest.approx(expected, rel=1e-9)


@given(views_and_weights(), st.floats(0.1, 5.0), st.data())
def test_more_weight_on_a_view_never_lowers_its_argmax(
    data: tuple[list[ViewRead], list[float]], extra: float, draw: st.DataObject
) -> None:
    views, weights = data
    candidates = [i for i, v in enumerate(views) if v.hypotheses]
    if not candidates:
        return
    i = draw.draw(st.sampled_from(candidates))
    favourite = views[i].hypotheses[0].tokens
    before = dict(probabilistic_fusion(views, weights).posterior)[favourite]
    heavier = list(weights)
    heavier[i] += extra
    after = dict(probabilistic_fusion(views, heavier).posterior)[favourite]
    assert after >= before - 1e-12


@given(views_and_weights())
def test_posteriors_are_distributions_over_valid_plates(
    data: tuple[list[ViewRead], list[float]],
) -> None:
    views, weights = data
    fused = probabilistic_fusion(views, weights)
    if fused.prediction is None:
        assert all(not v.hypotheses for v in views)
        return
    assert grammar.accepts(fused.prediction)
    assert math.fsum(p for _, p in fused.posterior) == pytest.approx(1.0)
    assert fused.posterior[0] == (fused.prediction, fused.confidence)
    assert [p.symbol for p in fused.positions] == list(fused.prediction)
    for position in fused.positions:
        assert math.fsum(p for _, p in position.distribution) == pytest.approx(1.0)
        assert 0.0 <= position.confidence <= 1.0


@given(views_and_weights())
def test_abstaining_views_change_nothing(data: tuple[list[ViewRead], list[float]]) -> None:
    views, weights = data
    base = probabilistic_fusion(views, weights)
    padded = probabilistic_fusion([*views, ViewRead()], [*weights, 2.0])
    assert padded.prediction == base.prediction
    assert dict(padded.posterior) == pytest.approx(dict(base.posterior))


def test_a_repeated_view_counts_like_double_weight() -> None:
    view = ViewRead(
        hypotheses=(Hypothesis("12-WW", math.log(0.7)), Hypothesis("13-WW", math.log(0.3)))
    )
    twice = probabilistic_fusion([view, view])
    double = probabilistic_fusion([view], [2.0])
    assert dict(twice.posterior) == pytest.approx(dict(double.posterior))
    assert dict(twice.posterior)["12-WW"] == pytest.approx(0.49 / (0.49 + 0.09))


def test_probabilistic_fusion_differs_from_the_vote_where_it_should() -> None:
    # Two weak views lean towards 13-WW, one confident view says 12-WW. The vote counts
    # views; fusion multiplies evidence and trusts the confident view.
    confident = ViewRead(
        hypotheses=(Hypothesis("12-WW", math.log(0.98)), Hypothesis("13-WW", math.log(0.02))),
        prediction="12-WW",
        confidence=0.98,
    )
    weak = ViewRead(
        hypotheses=(Hypothesis("13-WW", math.log(0.55)), Hypothesis("12-WW", math.log(0.45))),
        prediction="13-WW",
        confidence=0.55,
    )
    views = [confident, weak, weak]
    assert legacy_vote(views).prediction == "13-WW"
    fused = probabilistic_fusion(views)
    assert fused.prediction == "12-WW"
    assert fused.agreeing_views == 1


def test_per_position_posterior_highlights_the_uncertain_character() -> None:
    views = [
        ViewRead(
            hypotheses=(Hypothesis("12-WW", math.log(0.6)), Hypothesis("13-WW", math.log(0.4)))
        ),
        ViewRead(
            hypotheses=(Hypothesis("12-WW", math.log(0.9)), Hypothesis("112-WW", math.log(0.1)))
        ),
    ]
    fused = probabilistic_fusion(views)
    assert fused.prediction == "12-WW"
    by_index = {p.index: p for p in fused.positions}
    assert by_index[1].symbol == "2"
    assert by_index[1].confidence < 1.0
    assert dict(by_index[1].distribution).get("3", 0.0) > 0.0
    assert by_index[3].confidence == pytest.approx(1.0)
    assert GAP not in dict(by_index[0].distribution) or dict(by_index[0].distribution)[GAP] >= 0


def test_weights_validation_dispatch_and_quality() -> None:
    view = ViewRead(hypotheses=(Hypothesis("12-WW", 0.0),))
    with pytest.raises(ValueError):
        probabilistic_fusion([view], [1.0, 2.0])
    with pytest.raises(ValueError):
        probabilistic_fusion([view], [-1.0])
    with pytest.raises(ValueError):
        fuse([view], "median")
    assert fuse([view], "legacy_vote").method == "legacy_vote"
    assert fuse([view]).prediction == "12-WW"
    assert probabilistic_fusion([]).prediction is None
    assert quality_weight(0.0) == 0.0
    assert 0.0 < quality_weight(300.0) == pytest.approx(0.5)
    assert quality_weight(1e9, detector_confidence=0.5) == pytest.approx(0.5, rel=1e-3)


def test_fused_prediction_sets_follow_the_threshold() -> None:
    from plate_reader.fusion import fused_prediction_set

    posterior = [("12-WW", 0.9), ("13-WW", 0.1)]
    assert fused_prediction_set(posterior, None) is None
    assert fused_prediction_set(posterior, 0.15) == ("12-WW",)
    assert fused_prediction_set(posterior, 0.95) == ("12-WW", "13-WW")
    assert fused_prediction_set(posterior, 1.0) == ("12-WW", "13-WW")
    view = ViewRead(
        hypotheses=(Hypothesis("12-WW", math.log(0.9)), Hypothesis("13-WW", math.log(0.1)))
    )
    assert probabilistic_fusion([view], threshold=0.15).prediction_set == ("12-WW",)
    assert legacy_vote([view], threshold=0.15).prediction_set is None


def test_read_images_fuses_probabilistically_by_default_and_keeps_the_vote() -> None:
    from pathlib import Path

    import numpy as np

    from plate_reader import pipeline
    from plate_reader.detector import Detection
    from plate_reader.grammar import Plate
    from plate_reader.pipeline import PlateReading

    crop = np.zeros((16, 32, 3), dtype=np.uint8)
    # Two photos weakly read 13-WW twice each; one photo reads 12-WW with a confident detector.
    plan = {
        "a": [("13 WW", 0.55, 0.3)],
        "b": [("13 WW", 0.55, 0.3)],
        "c": [("12 WW", 0.9, 0.99)],
    }

    class Detector:
        def detect(self, path: Path) -> list[Detection]:
            return [Detection((0, 0, 32, 16), conf, crop) for _, _, conf in plan[Path(path).stem]]

    calls = iter([item for stem in "abc" for item in plan[stem]])

    def fake_read(backend: object, detection: Detection) -> PlateReading:
        text, weight, _ = next(calls)
        plate = Plate.from_tokens(text.replace(" ", "-"))
        return PlateReading(
            plate=plate, detection=detection, votes={text: weight * detection.confidence}
        )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(pipeline, "read_detection", fake_read)
    try:
        vote = pipeline.read_images(
            ["a", "b", "c"], detector=Detector(), backend=object(), fusion="vote"
        )  # type: ignore[arg-type]
        calls = iter([item for stem in "abc" for item in plan[stem]])
        fused = pipeline.read_images(
            ["a", "b", "c"], detector=Detector(), backend=object(), fusion="probabilistic"
        )  # type: ignore[arg-type]
        calls = iter([item for stem in "abc" for item in plan[stem]])
        auto = pipeline.read_images(["a", "b", "c"], detector=Detector(), backend=object())  # type: ignore[arg-type]
    finally:
        monkeypatch.undo()
    assert vote.fusion == "vote"
    assert vote.fused is None
    assert fused.fusion == "probabilistic"
    assert fused.fused is not None
    # EasyOCR's vote shares are not calibrated, so "auto" falls back to the vote (ADR 0009).
    assert auto.fusion == "vote"
    assert auto.text == vote.text
    assert fused.votes == vote.votes
    assert {vote.text, fused.text} <= {"12 WW", "13 WW"}
    with pytest.raises(ValueError):
        pipeline.read_images([], detector=Detector(), backend=object(), fusion="median")  # type: ignore[arg-type]
