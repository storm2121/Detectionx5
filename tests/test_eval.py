"""The evaluation harness with fake recognisers: metrics, bootstrap, sets, payload, report."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from typer.testing import CliRunner

from plate_reader.cli import app
from plate_reader.docs_render import SYNTHETIC_LABEL, RenderContext, render_text
from plate_reader.eval import Bootstrap, harness, recognizers, sets
from plate_reader.eval.metrics import ece, letter_confusion, reliability, score_reads, summarise
from plate_reader.eval.report import write_report
from plate_reader.fusion import legacy_vote
from plate_reader.hypotheses import Hypothesis, ViewRead, normalised
from plate_reader.imaging import Image
from plate_reader.strings import align, glyphs, levenshtein
from plate_reader.synthetic import write_crops, write_scenes


class TableRecognizer:
    """Answers from a lookup keyed by the image bytes: a perfect or a corrupting oracle."""

    name = "table"

    def __init__(self, answers: dict[bytes, str | None], confidence: float = 0.9) -> None:
        self.answers = answers
        self.confidence = confidence
        self.warmed = False

    @property
    def version(self) -> str:
        return "table-1"

    def warmup(self) -> None:
        self.warmed = True

    def read(self, image: Image) -> ViewRead:
        tokens = self.answers.get(image.tobytes())
        if tokens is None:
            return ViewRead()
        return ViewRead(
            hypotheses=(Hypothesis(tokens, math.log(self.confidence)),),
            prediction=tokens,
            confidence=self.confidence,
            latency_ms=1.0,
        )


def _corrupt(tokens: str) -> str:
    return tokens.replace(tokens[0], "9" if tokens[0] != "9" else "8", 1)


# --- strings ----------------------------------------------------------------------
@given(st.text("0123ب-", max_size=8), st.text("0123ب-", max_size=8))
def test_alignment_cost_equals_levenshtein(a: str, b: str) -> None:
    columns = align(a, b)
    cost = sum(1 for i, j in columns if i is None or j is None or a[i] != b[j])
    assert cost == levenshtein(a, b) == levenshtein(b, a)
    assert [a[i] for i, _ in columns if i is not None] == list(a)
    assert [b[j] for _, j in columns if j is not None] == list(b)


def test_glyphs_drop_separators() -> None:
    assert glyphs("24830-ب-1") == "24830ب1"
    assert levenshtein("abc", "abc") == 0


# --- bootstrap ---------------------------------------------------------------------
def test_bootstrap_is_seeded_and_brackets_the_estimate() -> None:
    values = np.array([1.0] * 70 + [0.0] * 30)
    a, b = Bootstrap(100, 500, seed=3).mean(values), Bootstrap(100, 500, seed=3).mean(values)
    assert a == b
    assert a.value == pytest.approx(0.7)
    assert a.ci_low < 0.7 < a.ci_high
    assert a.ci_low > 0.55
    assert a.ci_high < 0.85


def test_bootstrap_handles_nan_ratio_and_statistics() -> None:
    boot = Bootstrap(4, 200, seed=0)
    est = boot.mean([1.0, np.nan, 0.0, np.nan])
    assert est.n == 2
    assert est.value == pytest.approx(0.5)
    assert math.isnan(boot.mean([np.nan] * 4).value)
    assert boot.ratio([1, 1, 0, 0], [2, 2, 2, 2]).value == pytest.approx(0.25)
    stat = boot.statistic(lambda idx: float(len(idx)))
    assert stat.value == stat.ci_low == stat.ci_high == 4.0
    assert boot.describe("image")["unit"] == "image"
    with pytest.raises(ValueError):
        Bootstrap(0)
    assert est.as_dict()["n"] == 2


# --- metrics -------------------------------------------------------------------------
def test_scores_per_field_and_cer() -> None:
    truths = ["24830-ب-1", "24830-ب-1", "72173-WW", "1-أ-2"]
    reads = [
        ViewRead(prediction="24830-ب-1", confidence=0.9),
        ViewRead(prediction="24830-د-1", confidence=0.6),
        ViewRead(prediction="72173-WW", confidence=0.8, prediction_set=("72173-WW",)),
        ViewRead(),
    ]
    scores = score_reads(truths, reads)
    assert scores["exact"].tolist() == [1.0, 0.0, 1.0, 0.0]
    assert scores["digits"].tolist() == [1.0, 1.0, 1.0, 0.0]
    assert scores["letter"][2] != scores["letter"][2]  # NaN for a temporary truth
    assert scores["letter"][1] == 0.0
    assert scores["edits"].tolist() == [0.0, 1.0, 0.0, 3.0]
    assert scores["glyphs"].tolist() == [7.0, 7.0, 7.0, 3.0]
    assert scores["confidence"][3] == 0.0
    assert scores["covered"][2] == 1.0
    with pytest.raises(ValueError):
        score_reads(truths, reads[:2])


def test_ece_and_reliability() -> None:
    conf = np.array([0.95, 0.95, 0.05, 0.05])
    correct = np.array([1.0, 1.0, 0.0, 0.0])
    assert ece(conf, correct) == pytest.approx(0.05)
    assert math.isnan(ece(np.array([]), np.array([])))
    bins = reliability(conf, correct)
    assert sum(b["n"] for b in bins) == 4
    assert bins[9]["accuracy"] == 1.0


def test_letter_confusion_counts_rows_by_truth() -> None:
    truths = ["1-ب-1", "1-ب-1", "1-WW"]
    reads = [ViewRead(prediction="1-ب-1"), ViewRead(prediction=None), ViewRead(prediction="1-WW")]
    confusion = letter_confusion(truths, reads)
    row = confusion["rows"].index("ب")
    assert confusion["matrix"][row][confusion["columns"].index("ب")] == 1
    assert confusion["matrix"][row][confusion["columns"].index("none")] == 1
    assert sum(map(sum, confusion["matrix"])) == 2


def test_summary_carries_every_metric_with_intervals() -> None:
    truths = ["24830-ب-1"] * 5 + ["72173-WW"] * 5
    reads = [ViewRead(prediction=t, confidence=0.8, prediction_set=(t,)) for t in truths]
    summary = summarise(truths, reads, Bootstrap(10, 200, seed=1))
    for key in (
        "exact_match",
        "digits_accuracy",
        "letter_accuracy",
        "cer",
        "ece",
        "coverage",
        "set_size",
    ):
        assert key in summary["metrics"]
    assert summary["metrics"]["exact_match"]["value"] == 1.0
    assert summary["metrics"]["letter_accuracy"]["n"] == 5
    assert summary["latency_ms"]["p50"] == 0.0


# --- fusion baseline ------------------------------------------------------------------
def test_legacy_vote_matches_the_old_api_semantics() -> None:
    views = [
        ViewRead(prediction="24830-ب-1", votes=(("24830-ب-1", 4.0),)),
        ViewRead(prediction="24830-ب-1", votes=(("24830-ب-1", 3.0), ("24830-ب-1", 1.0))),
        ViewRead(prediction="12345-أ-2", votes=(("12345-أ-2", 2.0),)),
    ]
    fused = legacy_vote(views)
    assert fused.prediction == "24830-ب-1"
    assert fused.confidence == pytest.approx(0.8)
    assert fused.agreeing_views == 2
    assert legacy_vote([]).prediction is None
    from_confidence = legacy_vote([ViewRead(prediction="1-WW", confidence=0.4)])
    assert from_confidence.prediction == "1-WW"
    assert from_confidence.confidence == pytest.approx(1.0)
    assert legacy_vote([ViewRead(prediction="1-WW")], weights=[0.5]).prediction == "1-WW"


def test_normalised_hypotheses_are_log_shares() -> None:
    hyps = normalised({"1-WW": 3.0, "2-WW": 1.0, "3-WW": 0.0})
    assert [h.tokens for h in hyps] == ["1-WW", "2-WW"]
    assert hyps[0].probability == pytest.approx(0.75)
    assert normalised({}) == ()


# --- sets, harness, report, docs -----------------------------------------------------
@pytest.fixture
def small_set() -> sets.EvalSet:
    return sets.synthetic_set(12, seed=77)


def test_harness_payload_with_fake_recognisers(small_set: sets.EvalSet, tmp_path: Path) -> None:
    perfect = TableRecognizer({it.image.tobytes(): it.truth for it in small_set.items})
    noisy = TableRecognizer(
        {
            it.image.tobytes(): (_corrupt(it.truth) if i % 3 == 0 else it.truth)
            for i, it in enumerate(small_set.items)
        }
    )
    noisy.name = "noisy"
    views = sets.view_sets(4, 3, seed=78)
    answers = {it.image.tobytes(): it.truth for it in views.items}
    perfect.answers.update(answers)
    noisy.answers.update(
        {k: (_corrupt(v) if i % 2 else v) for i, (k, v) in enumerate(answers.items())}
    )
    payload = harness.build_payload(
        small_set,
        [perfect, noisy],
        resamples=200,
        confidence=0.95,
        seed=0,
        views=views,
        ks=(1, 3),
        quiet=True,
    )
    assert perfect.warmed
    assert payload["label"] == SYNTHETIC_LABEL
    assert payload["set"]["kind"] == "synthetic"
    assert payload["recognizers"]["table"]["metrics"]["exact_match"]["value"] == 1.0
    assert payload["recognizers"]["noisy"]["metrics"]["exact_match"]["value"] == pytest.approx(
        8 / 12
    )
    diff = payload["comparisons"]["noisy - table"]["exact_match_difference"]
    assert diff["value"] == pytest.approx(-4 / 12)
    methods = payload["fusion"]["recognizers"]["table"]["methods"]
    assert set(methods) == {"legacy_vote", "probabilistic", "probabilistic_weighted"}
    assert methods["probabilistic"]["k=3"]["metrics"]["exact_match"]["value"] == 1.0
    fusion = methods["legacy_vote"]
    assert fusion["k=3"]["metrics"]["exact_match"]["value"] == 1.0
    assert payload["fusion"]["n_sets"] == 4

    path = harness.write_payload(payload, tmp_path / "eval_synthetic.json")
    assert json.loads(path.read_text(encoding="utf-8"))["schema"] == harness.SCHEMA
    report = write_report(payload, tmp_path / "eval_synthetic.html")
    assert "Synthetic results are not real-world accuracy" in report.read_text(encoding="utf-8")

    ctx = RenderContext(root=tmp_path.parent)
    ctx._json_cache["eval_synthetic"] = payload
    rendered, problems = render_text(
        "<!-- BEGIN RENDER synthetic-baseline -->\n<!-- END RENDER synthetic-baseline -->\n", ctx
    )
    assert problems == []
    assert "| table | `table-1` | 1.000" in rendered
    assert "| table | legacy_vote |" in rendered
    assert SYNTHETIC_LABEL.capitalize() in rendered


def test_folder_sets_keep_their_synthetic_kind(tmp_path: Path) -> None:
    write_crops(tmp_path / "crops", 5, seed=1)
    crop_set = sets.crops_folder_set(tmp_path / "crops" / "labels.csv")
    assert crop_set.kind == "synthetic"
    assert len(crop_set.items) == 5

    write_scenes(tmp_path / "scenes", 6, seed=2)
    data = sets.data_set(tmp_path / "scenes")
    assert data.kind == "synthetic"  # the manifest marks a generated stand-in for data/
    assert data.items
    assert all(it.image.size for it in data.items)


def test_data_set_without_boxes_uses_the_detector(tmp_path: Path) -> None:
    write_scenes(tmp_path / "scenes", 4, seed=3)
    labels = tmp_path / "scenes" / "eval" / "labels.csv"
    lines = labels.read_text(encoding="utf-8").splitlines()
    stripped = [lines[0]] + [",".join([*line.split(",")[:3], "", "", "", ""]) for line in lines[1:]]
    labels.write_text("\n".join(stripped) + "\n", encoding="utf-8")
    assert sets.data_set(tmp_path / "scenes").items == []
    found = sets.data_set(tmp_path / "scenes", detect=lambda image: [((0, 0, 40, 20), 0.9)])
    assert len(found.items) == len(stripped) - 1
    none = sets.data_set(tmp_path / "scenes", detect=lambda image: [])
    assert none.info["skipped_without_box"] == len(stripped) - 1


def test_registry_and_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def factory(**_: object) -> TableRecognizer:
        return TableRecognizer({})

    monkeypatch.setitem(recognizers.REGISTRY, "table", factory)
    with pytest.raises(ValueError):
        recognizers.build("nope")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "eval",
            "--set",
            "synthetic",
            "--n",
            "4",
            "--views",
            "2",
            "--k",
            "3",
            "-r",
            "table",
            "--resamples",
            "100",
            "--out",
            str(tmp_path),
            "--device",
            "cpu",
            "--quiet",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads((tmp_path / "eval_synthetic.json").read_text(encoding="utf-8"))
    assert payload["recognizers"]["table"]["metrics"]["read_rate"]["value"] == 0.0
    assert (tmp_path / "eval_synthetic.html").exists()
    for name, extra in (("pseudo_real", []), ("views", ["--views", "2"])):
        result = runner.invoke(
            app,
            [
                "eval",
                "--set",
                name,
                "--n",
                "3",
                "-r",
                "table",
                "--resamples",
                "100",
                "--out",
                str(tmp_path),
                "--quiet",
                *extra,
            ],
        )
        assert result.exit_code == 0, result.output
    assert (tmp_path / "eval_views.json").exists()
    empty = runner.invoke(
        app, ["eval", "--set", "data", "-r", "table", "--data-dir", str(tmp_path / "nothing")]
    )
    assert empty.exit_code != 0
    write_crops(tmp_path / "crops", 3, seed=1)
    folder = runner.invoke(
        app,
        [
            "eval",
            "--crops",
            str(tmp_path / "crops"),
            "-r",
            "table",
            "--resamples",
            "100",
            "--out",
            str(tmp_path),
            "--quiet",
        ],
    )
    assert folder.exit_code == 0, folder.output


def test_read_cache_round_trips_and_is_used_for_cacheable_recognisers(tmp_path: Path) -> None:
    from plate_reader.eval.cache import ReadCache

    cache = ReadCache(tmp_path / "cache")
    read = ViewRead(
        hypotheses=(Hypothesis("1-WW", -0.1),),
        prediction="1-WW",
        confidence=0.9,
        prediction_set=("1-WW",),
        votes=(("1 WW", 2.0),),
        latency_ms=3.0,
        extra={"segmented": True},
    )
    key = ReadCache.key("x", "1", np.zeros((2, 3, 3), dtype=np.uint8))
    assert cache.get(key) is None
    cache.put(key, read)
    assert cache.get(key) == read
    assert (cache.hits, cache.misses) == (1, 1)

    items = sets.synthetic_set(3, seed=5).items
    counter = TableRecognizer({it.image.tobytes(): it.truth for it in items})
    counter.cacheable = True  # type: ignore[attr-defined]
    calls: list[int] = []
    original = counter.read

    def counting(image: Image) -> ViewRead:
        calls.append(1)
        return original(image)

    counter.read = counting  # type: ignore[method-assign]
    first = harness.read_all(items, [counter], "x", quiet=True, cache=cache)
    second = harness.read_all(items, [counter], "x", quiet=True, cache=cache)
    assert first == second
    assert len(calls) == 3
