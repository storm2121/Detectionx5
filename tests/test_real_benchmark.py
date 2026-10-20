"""The real-photo benchmark's machinery (ADR 0013), on synthetic fixtures only.

A grouped bootstrap that draws whole groups, the ``group`` column and the set card, photos
read end to end with the labelled boxes ignored, a photo without a detection scored as
nothing read.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from typer.testing import CliRunner

from plate_reader.cli import app, evaluate
from plate_reader.detector import pad_box
from plate_reader.eval import Bootstrap, harness, recognizers, sets
from plate_reader.hypotheses import Hypothesis, ViewRead
from plate_reader.imaging import Image
from plate_reader.normalize import parse_plate

PLATE_A = "24830-ب-1"
PLATE_B = "72173 WW"


def _tokens(text: str) -> str:
    plate = parse_plate(text)
    assert plate is not None
    return plate.tokens


class Oracle:
    """Reads a crop right when its pixels were registered, and counts what it was asked."""

    name = "oracle"
    version = "oracle-1"

    def __init__(self, answers: dict[bytes, str], with_sets: bool = False) -> None:
        self.answers = answers
        self.calls = 0
        if with_sets:
            self.conformal_threshold = 0.5

    def read(self, image: Image) -> ViewRead:
        self.calls += 1
        tokens = self.answers.get(image.tobytes())
        if tokens is None:
            return ViewRead(prediction_set=() if hasattr(self, "conformal_threshold") else None)
        return ViewRead(
            hypotheses=(Hypothesis(tokens, math.log(0.9)),),
            prediction=tokens,
            confidence=0.9,
            prediction_set=(tokens,) if hasattr(self, "conformal_threshold") else None,
            latency_ms=1.0,
        )


# --- the grouped bootstrap ------------------------------------------------------------
def test_a_grouped_bootstrap_draws_whole_groups() -> None:
    groups = ["a", "a", "a", "b", "b", "c"]
    values = np.array([1.0, 1.0, 1.0, 0.0, 0.0, 1.0])
    boot = Bootstrap(6, resamples=300, seed=4, groups=groups)
    assert boot.grouped
    assert boot.n_groups == 3
    weights = boot.weights
    assert weights is not None
    # the members of a group are drawn together, and every resample draws three groups
    assert np.array_equal(weights[:, 0], weights[:, 1])
    assert np.array_equal(weights[:, 0], weights[:, 2])
    assert np.array_equal(weights[:, 3], weights[:, 4])
    assert np.all(weights[:, [0, 3, 5]].sum(axis=1) == 3)
    estimate = boot.mean(values)
    assert estimate.value == pytest.approx(4 / 6)
    assert estimate.ci_low <= estimate.value <= estimate.ci_high
    ratio = boot.ratio(values, np.ones(6))
    assert ratio.value == pytest.approx(4 / 6)
    sizes = boot.statistic(lambda idx: float(len(idx)))
    assert sizes.value == 6.0
    assert sizes.ci_low < sizes.ci_high  # groups of unequal size: resamples differ in length
    described = boot.describe("image")
    assert described["unit"] == "group"
    assert described["groups"] == 3
    assert described["grouped_units"] == "image"
    with pytest.raises(ValueError, match="one group label per unit"):
        Bootstrap(3, groups=[0, 1])


def test_clustered_units_get_the_wider_interval_they_deserve() -> None:
    values = np.repeat([1.0, 0.0] * 5, 10)  # ten groups of ten identical units
    groups = np.repeat(np.arange(10), 10).tolist()
    flat = Bootstrap(100, resamples=1000, seed=0).mean(values)
    clustered = Bootstrap(100, resamples=1000, seed=0, groups=groups).mean(values)
    assert flat.value == clustered.value == 0.5
    assert clustered.ci_high - clustered.ci_low > 2 * (flat.ci_high - flat.ci_low)


def test_an_ungrouped_bootstrap_draws_exactly_as_before() -> None:
    boot = Bootstrap(5, resamples=50, seed=7)
    expected = np.random.default_rng(7).integers(0, 5, size=(50, 5))
    assert np.array_equal(boot.indices, expected)
    assert not boot.grouped
    assert boot.describe("image")["unit"] == "image"
    assert "groups" not in boot.describe("image")


# --- the data set: groups and the card --------------------------------------------------
def _photo(path: Path, seed: int) -> Image:
    rng = np.random.default_rng(seed)
    image = rng.integers(0, 255, size=(100, 200, 3), dtype=np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)
    loaded = cv2.imread(str(path), cv2.IMREAD_COLOR)
    assert loaded is not None
    return loaded


BOX_A = (10, 10, 90, 40)
BOX_B = (110, 50, 190, 90)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Three photos: one with two plates, one with plate A, one with plate B; two groups."""
    root = tmp_path / "data"
    for i in range(3):
        _photo(root / "eval" / "images" / f"p{i}.png", i)
    a, b = ",".join(map(str, BOX_A)), ",".join(map(str, BOX_B))
    (root / "eval" / "labels.csv").write_text(
        "image_path,plate_text,format,x1,y1,x2,y2,group\n"
        f"images/p0.png,{PLATE_A},standard,{a},g1\n"
        f"images/p0.png,{PLATE_B},temporary,{b},g1\n"
        f"images/p1.png,{PLATE_A},standard,{a},g1\n"
        f"images/p2.png,{PLATE_B},temporary,{b},g2\n",
        encoding="utf-8",
    )
    (root / "eval" / "card.json").write_text(
        json.dumps({"description": "three generated photos", "photos": 3}), encoding="utf-8"
    )
    return root


def test_the_labelled_set_carries_groups_photos_and_the_card(data_dir: Path) -> None:
    labelled = sets.data_set(data_dir)
    assert labelled.kind == "data"
    assert labelled.grouped
    assert [item.group for item in labelled.items] == [0, 0, 0, 1]
    assert labelled.info["photos"] == 3
    assert labelled.info["groups"] == 2
    assert labelled.info["card"] == {"description": "three generated photos", "photos": 3}

    labels = data_dir / "eval" / "labels.csv"
    lines = labels.read_text(encoding="utf-8").splitlines()
    labels.write_text("\n".join(line.rsplit(",", 1)[0] for line in lines) + "\n", encoding="utf-8")
    (data_dir / "eval" / "card.json").unlink()
    plain = sets.data_set(data_dir)
    assert not plain.grouped
    assert "groups" not in plain.info
    assert "card" not in plain.info


def _served(image: Image, box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    h, w = image.shape[:2]
    return pad_box([float(v) for v in box], w, h)


def test_photos_are_read_end_to_end_with_the_labelled_boxes_ignored(data_dir: Path) -> None:
    photos = [
        cv2.imread(str(data_dir / "eval" / "images" / f"p{i}.png"), cv2.IMREAD_COLOR)
        for i in range(3)
    ]
    detections: dict[bytes, list[tuple[tuple[int, int, int, int], float]]] = {
        # the photo with two plates: the more confident detection lies on plate B
        photos[0].tobytes(): [(_served(photos[0], BOX_A), 0.4), (_served(photos[0], BOX_B), 0.8)],
        # a detection on no labelled plate
        photos[1].tobytes(): [((150, 0, 199, 20), 0.9)],
        # nothing found
        photos[2].tobytes(): [],
    }
    end_to_end = sets.data_photos_set(data_dir, lambda image: detections[image.tobytes()])
    assert end_to_end.grouped
    assert [item.truth for item in end_to_end.items] == [
        _tokens(PLATE_B),
        _tokens(PLATE_A),
        _tokens(PLATE_B),
    ]
    two, off, missed = end_to_end.items
    x1, y1, x2, y2 = _served(photos[0], BOX_B)
    assert np.array_equal(two.image, photos[0][y1:y2, x1:x2])
    assert two.meta["on_plate"] == 1.0
    assert two.meta["iou"] == 1.0
    assert two.meta["detector_confidence"] == 0.8
    assert off.meta["on_plate"] == 0.0
    assert missed.image.size == 0
    assert missed.meta == {"box": "none", "on_plate": 0.0}
    assert end_to_end.info["no_detection"] == 1
    assert end_to_end.info["plates"] == 4
    assert end_to_end.info["photos"] == 3
    assert end_to_end.info["read"].startswith("end to end")


def test_a_photo_without_a_crop_is_scored_as_nothing_read(data_dir: Path) -> None:
    photo = cv2.imread(str(data_dir / "eval" / "images" / "p1.png"), cv2.IMREAD_COLOR)
    crop = photo[10:40, 10:90].copy()
    items = [
        sets.EvalItem("seen", crop, _tokens(PLATE_A), group=0, meta={"on_plate": 1.0}),
        sets.EvalItem("missed", sets.NO_CROP, _tokens(PLATE_B), group=1, meta={"on_plate": 0.0}),
    ]
    eval_set = sets.EvalSet("data", "data", items, {"photos": 2}, grouped=True)
    oracle = Oracle({crop.tobytes(): _tokens(PLATE_A)}, with_sets=True)
    payload = harness.build_payload(eval_set, [oracle], resamples=200, confidence=0.95, seed=0)
    assert oracle.calls == 1  # the photo without a crop is never handed to the recogniser
    metrics = payload["recognizers"]["oracle"]["metrics"]
    assert metrics["exact_match"]["value"] == 0.5
    assert metrics["read_rate"]["value"] == 0.5
    assert metrics["coverage"]["value"] == 0.5  # nothing read: an empty set, not a skipped one
    assert payload["bootstrap"]["unit"] == "group"
    assert payload["bootstrap"]["groups"] == 2
    detection = payload["detection"]
    assert detection["photos"] == 2
    assert detection["no_detection"] == 1
    assert detection["off_plate"] == 0
    assert detection["on_plate"]["value"] == 0.5
    assert harness.nothing_read(Oracle({})).prediction_set is None
    assert math.isnan(harness.nothing_read(oracle).latency_ms)


def test_plate_eval_detect_writes_the_end_to_end_results(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path, tmp_path: Path
) -> None:
    class Blank:
        name = "blank"
        version = "blank-1"

        def read(self, image: Any) -> ViewRead:
            return ViewRead()

    monkeypatch.setitem(recognizers.REGISTRY, "blank", lambda **_: Blank())
    monkeypatch.setattr(
        evaluate, "_detector_for_photos", lambda settings: lambda image: [(BOX_A, 0.7)]
    )
    runner = CliRunner()
    common = ["-r", "blank", "--views", "0", "--resamples", "100", "--quiet"]
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "eval",
            "--set",
            "data",
            "--data-dir",
            str(data_dir),
            "--detect",
            "--out",
            str(out),
            *common,
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads((out / "eval_data_e2e.json").read_text(encoding="utf-8"))
    assert payload["set"]["n"] == 3
    assert payload["set"]["plates"] == 4
    assert payload["set"]["no_detection"] == 0
    assert payload["detection"]["photos"] == 3
    assert payload["bootstrap"]["unit"] == "group"
    assert payload["set"]["card"]["description"] == "three generated photos"

    labelled = runner.invoke(
        app, ["eval", "--set", "data", "--data-dir", str(data_dir), "--out", str(out), *common]
    )
    assert labelled.exit_code == 0, labelled.output
    assert json.loads((out / "eval_data.json").read_text(encoding="utf-8"))["set"]["n"] == 4

    wrong_set = runner.invoke(app, ["eval", "--set", "synthetic", "--detect", *common])
    assert wrong_set.exit_code != 0
    monkeypatch.setattr(evaluate, "_detector_for_photos", lambda settings: None)
    no_model = runner.invoke(
        app, ["eval", "--set", "data", "--data-dir", str(data_dir), "--detect", *common]
    )
    assert no_model.exit_code != 0
