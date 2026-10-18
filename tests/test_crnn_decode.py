"""CTC decoding, temperature scaling and conformal sets on hand-built and random logits."""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from plate_reader import grammar
from plate_reader.crnn import charset
from plate_reader.crnn.calibrate import fit_temperature, mean_nll, posterior, probability_of
from plate_reader.crnn.conformal import (
    evaluate_coverage,
    nonconformity,
    prediction_set,
    quantile,
    scores_of,
)
from plate_reader.crnn.decode import (
    constrained_beam_search,
    ctc_log_likelihood,
    greedy,
    log_softmax,
    prefix_beam_search,
)
from plate_reader.hypotheses import Hypothesis

C = charset.NUM_CLASSES


def path_logits(path: list[int], peak: float = 8.0, frames: int | None = None) -> np.ndarray:
    """Logits whose argmax follows ``path`` (class indices), padded with blanks."""
    frames = frames or len(path)
    logits = np.zeros((frames, C))
    for t in range(frames):
        logits[t, path[t] if t < len(path) else charset.BLANK] = peak
    return logits


def spell(tokens: str, blank_between: bool = True) -> list[int]:
    out: list[int] = []
    for index in charset.encode(tokens):
        out += [index, charset.BLANK] if blank_between else [index]
    return out


def test_charset_follows_the_grammar() -> None:
    assert charset.CLASSES[0] == "<blank>"
    assert charset.CLASSES[1:] == grammar.SYMBOLS
    assert charset.decode(charset.encode("24830-ب-1")) == "24830-ب-1"
    assert charset.decode([0, 0]) == ""


def test_log_softmax_normalises_and_temperature_flattens() -> None:
    logits = np.random.default_rng(0).normal(size=(5, C)) * 3
    lp = log_softmax(logits)
    assert np.allclose(np.exp(lp).sum(axis=-1), 1.0)
    sharp, flat = log_softmax(logits, 0.5), log_softmax(logits, 4.0)
    assert sharp.max() > lp.max() > flat.max()


def test_greedy_collapses_repeats_and_needs_blanks_for_doubles() -> None:
    two = charset.encode("2")[0]
    assert greedy(log_softmax(path_logits([two, two, 0, two])))[0] == "22"
    assert greedy(log_softmax(path_logits([two, two, two])))[0] == "2"
    assert greedy(log_softmax(path_logits([0, 0])))[0] == ""


def test_beam_matches_greedy_on_a_clear_path_and_constrains_the_output() -> None:
    lp = log_softmax(path_logits(spell("24830-ب-1"), frames=40))
    assert greedy(lp)[0] == "24830-ب-1"
    beam = constrained_beam_search(lp)
    assert beam[0].tokens == "24830-ب-1"
    assert all(grammar.accepts(h.tokens) for h in beam)
    assert prefix_beam_search(lp)[0].tokens == "24830-ب-1"


def test_constrained_beam_repairs_what_greedy_gets_wrong() -> None:
    # The letter frame prefers the digit 9 (the Kufi waw looks like a 9), but only a
    # letter is legal between the separators.
    logits = path_logits(spell("123-و-4"), frames=24)
    nine, waw = charset.encode("9")[0], charset.encode("و")[0]
    letter_frame = 8
    logits[letter_frame, waw] = 7.0
    logits[letter_frame, nine] = 8.0
    lp = log_softmax(logits)
    assert greedy(lp)[0] == "123-9-4"
    assert not grammar.accepts(greedy(lp)[0])
    assert constrained_beam_search(lp)[0].tokens == "123-و-4"


@settings(max_examples=60)
@given(arrays(np.float64, (8, C), elements=st.floats(-4, 4)))
def test_constrained_beam_only_returns_plates_and_never_exceeds_exact_mass(
    logits: np.ndarray,
) -> None:
    lp = log_softmax(logits)
    for hyp in constrained_beam_search(lp, beam_width=6):
        assert grammar.accepts(hyp.tokens)
        assert hyp.logp <= ctc_log_likelihood(lp, hyp.tokens) + 1e-9
    for hyp in prefix_beam_search(lp, beam_width=6):
        assert hyp.logp <= ctc_log_likelihood(lp, hyp.tokens) + 1e-9


def test_wide_beam_recovers_the_exact_probability() -> None:
    lp = log_softmax(np.random.default_rng(3).normal(size=(5, C)) * 2)
    beam = prefix_beam_search(lp, beam_width=400, prune=-math.inf)
    for hyp in beam[:5]:
        assert hyp.logp == pytest.approx(ctc_log_likelihood(lp, hyp.tokens), abs=1e-9)


def test_numpy_ctc_forward_matches_torch() -> None:
    torch = pytest.importorskip("torch")
    rng = np.random.default_rng(1)
    lp = log_softmax(rng.normal(size=(12, C)))
    for tokens in ("12-WW", "1-ب-22", "7"):
        target = torch.tensor([charset.encode(tokens)])
        loss = torch.nn.functional.ctc_loss(
            torch.from_numpy(lp)[:, None, :],
            target,
            torch.tensor([12]),
            torch.tensor([len(tokens)]),
            blank=0,
            reduction="sum",
        )
        assert ctc_log_likelihood(lp, tokens) == pytest.approx(-float(loss), abs=1e-8)


# --- calibration ---------------------------------------------------------------------------
def test_posterior_and_nll() -> None:
    hyps = (Hypothesis("1-WW", math.log(0.6)), Hypothesis("7-WW", math.log(0.2)))
    dist = posterior(hyps)
    assert dist[0] == ("1-WW", pytest.approx(0.75))
    assert probability_of(hyps, "7-WW") == pytest.approx(0.25)
    assert probability_of(hyps, "2-WW") == 0.0
    assert mean_nll([hyps], ["1-WW"]) == pytest.approx(-math.log(0.75))
    assert posterior(()) == []


def test_temperature_fit_softens_an_overconfident_model() -> None:
    # The digit frame scores the truth 9 and a wrong digit 12 on a third of the images,
    # and the reverse otherwise: the top read is right two times in three but reported
    # at about 0.95, so the NLL-optimal temperature must flatten (T > 1).
    rng = np.random.default_rng(5)
    truths, logits = [], []
    for i in range(60):
        tokens = grammar.random_plate(rng, "temporary")
        frames = path_logits(spell(tokens), peak=12.0, frames=20)
        true_class = charset.encode(tokens[0])[0]
        wrong_class = charset.encode("8" if tokens[0] != "8" else "7")[0]
        frames[0, true_class], frames[0, wrong_class] = (9.0, 12.0) if i % 3 == 0 else (12.0, 9.0)
        logits.append(frames)
        truths.append(tokens)
    fit = fit_temperature(
        lambda t: [log_softmax(x, t) for x in logits],
        truths,
        lambda lp: constrained_beam_search(lp, 6),
    )
    assert fit.nll_after < fit.nll_before
    assert fit.temperature > 1.5
    assert fit.as_dict()["evaluations"] == fit.evaluations


# --- conformal --------------------------------------------------------------------------
def test_conservative_quantile() -> None:
    scores = np.linspace(0.1, 0.9, 9)
    assert quantile(scores, 0.1) == pytest.approx(0.9)  # rank ceil(10 * 0.9) = 9
    assert quantile(scores[:8], 0.1) == 1.0  # rank 9 > n: the set must hold everything
    assert quantile([], 0.1) == 1.0


def test_scores_are_complements_without_rounding_to_zero() -> None:
    hyps = (Hypothesis("1-WW", 0.0), Hypothesis("2-WW", -60.0))
    scores = dict(scores_of(hyps))
    assert 0.0 < scores["1-WW"] < 1e-20  # 1 - q would round to exactly 0
    assert scores["2-WW"] == pytest.approx(1.0)
    assert nonconformity(hyps, "3-WW") == 1.0
    assert prediction_set(hyps, 1e-10).members == ("1-WW",)
    assert prediction_set(hyps, 1.0).covers_everything
    assert prediction_set(hyps, 0.0).size == 0


def _calibrated_beams(
    rng: np.random.Generator, n: int
) -> tuple[list[tuple[Hypothesis, ...]], list[str]]:
    """Beams whose posterior is calibrated by construction: the truth is drawn from it."""
    beams, truths = [], []
    for _ in range(n):
        probs = rng.dirichlet(np.full(5, 0.4))
        names = [f"{d}-WW" for d in rng.choice(np.arange(1, 999), size=5, replace=False)]
        beams.append(
            tuple(
                Hypothesis(t, math.log(max(p, 1e-300))) for t, p in zip(names, probs, strict=True)
            )
        )
        truths.append(names[int(rng.choice(5, p=probs))])
    return beams, truths


def test_split_conformal_covers_at_the_nominal_level() -> None:
    rng = np.random.default_rng(11)
    cal_beams, cal_truths = _calibrated_beams(rng, 1500)
    test_beams, test_truths = _calibrated_beams(rng, 1500)
    scores = [nonconformity(b, t) for b, t in zip(cal_beams, cal_truths, strict=True)]
    for alpha in (0.1, 0.05):
        report = evaluate_coverage(scores, test_beams, test_truths, alpha, resamples=300, seed=2)
        assert report.coverage.ci_low <= 1 - alpha <= report.coverage.ci_high
        assert report.coverage.value >= 1 - alpha - 0.03
        assert 1.0 <= report.set_size.value <= 5.0
        assert report.as_dict()["level"] == pytest.approx(1 - alpha)


def test_coverage_when_the_threshold_must_cover_everything() -> None:
    beams = [(Hypothesis("1-WW", 0.0),)]
    report = evaluate_coverage([0.5], beams, ["2-WW"], alpha=0.1, resamples=50)
    assert report.threshold == 1.0
    assert report.coverage.value == 1.0
    assert report.covers_everything_rate == 1.0
