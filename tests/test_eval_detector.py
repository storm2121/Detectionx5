"""``plate eval-detector`` with a stand-in for Ultralytics: what is asked, written and labelled.

The real Ultralytics path runs in ``tests/test_detector_runs.py`` (opt-in, on CPU); these
tests check the wiring around it without loading a model.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pytest
from typer.testing import CliRunner

from plate_reader.cli import app
from plate_reader.docs_render import SYNTHETIC_LABEL
from plate_reader.eval.detector import SCHEMA, display_path, evaluate_detector, split_images
from plate_reader.settings import PROJECT_ROOT
from plate_reader.synthetic import write_scenes


class FakeBox:
    mp = 0.75
    mr = 0.875
    map50 = 0.8125
    map = 0.5


class FakeMetrics:
    box = FakeBox()
    nt_per_class = np.array([3])
    nt_per_image = np.array([3])


class FakeYOLO:
    calls: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, weights: str) -> None:
        self.weights = weights

    def val(self, **kwargs: Any) -> FakeMetrics:
        FakeYOLO.calls.append({"weights": self.weights, **kwargs})
        return FakeMetrics()


@pytest.fixture
def fake_ultralytics(monkeypatch: pytest.MonkeyPatch) -> type[FakeYOLO]:
    FakeYOLO.calls = []
    module = types.ModuleType("ultralytics")
    module.YOLO = FakeYOLO  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ultralytics", module)
    return FakeYOLO


@pytest.fixture(scope="module")
def scenes(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("scenes")
    write_scenes(root, 8, 1005, val_fraction=0.5)
    return root / "detector.yaml"


def test_validation_reports_metrics_counts_and_provenance(
    scenes: Path, fake_ultralytics: type[FakeYOLO], tmp_path: Path
) -> None:
    payload = evaluate_detector(
        scenes, Path("models/best.pt"), imgsz=320, device="cpu", project=tmp_path
    )
    assert payload["schema"] == SCHEMA
    assert payload["label"] == SYNTHETIC_LABEL
    assert payload["metrics"] == {
        "precision": 0.75,
        "recall": 0.875,
        "map50": 0.8125,
        "map50_95": 0.5,
    }
    val_images = len(list((scenes.parent / "detector" / "images" / "val").iterdir()))
    assert payload["counts"] == {"images": val_images, "plates": 3, "images_with_plates": 3}
    assert payload["set"]["seed"] == 1005
    assert payload["set"]["n"] == 8
    assert payload["interval"].startswith("none")
    (call,) = fake_ultralytics.calls
    assert call["weights"] == str(Path("models/best.pt"))
    assert call["workers"] == 0
    assert call["split"] == "val"
    assert call["plots"] is False
    assert call["data"] == str(scenes.resolve())


def test_split_folders_resolve_like_the_data_layout(tmp_path: Path) -> None:
    (tmp_path / "detector" / "images" / "val").mkdir(parents=True)
    for name in ("a.jpg", "b.PNG", "notes.txt"):
        (tmp_path / "detector" / "images" / "val" / name).write_bytes(b"")
    yaml_path = tmp_path / "detector.yaml"
    yaml_path.write_text("val: detector/images/val\ntrain: [a, b]\n", encoding="utf-8")
    assert split_images(yaml_path, "val") == 2
    assert split_images(yaml_path, "train") is None
    assert split_images(yaml_path, "test") is None
    yaml_path.write_text(
        f"path: {tmp_path.as_posix()}\nval: detector/images/val\n", encoding="utf-8"
    )
    assert split_images(yaml_path, "val") == 2
    yaml_path.write_text("path: elsewhere\nval: detector/images/val\n", encoding="utf-8")
    assert split_images(yaml_path, "val") is None


def test_paths_are_shown_relative_to_the_project() -> None:
    assert display_path(PROJECT_ROOT / "synthetic" / "x" / "detector.yaml") == (
        "synthetic/x/detector.yaml"
    )
    assert display_path(Path(PROJECT_ROOT.anchor) / "outside" / "detector.yaml") in {
        "detector.yaml",
        "outside/detector.yaml",
    }


def test_cli_labels_synthetic_and_supplied_sets(
    scenes: Path, fake_ultralytics: type[FakeYOLO], tmp_path: Path
) -> None:
    runner = CliRunner()
    out = tmp_path / "synthetic.json"
    result = runner.invoke(app, ["eval-detector", "--data", str(scenes), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert SYNTHETIC_LABEL in result.output
    assert json.loads(out.read_text(encoding="utf-8"))["label"] == SYNTHETIC_LABEL

    supplied = tmp_path / "supplied"
    (supplied / "detector" / "images" / "val").mkdir(parents=True)
    (supplied / "detector.yaml").write_text("val: detector/images/val\n", encoding="utf-8")
    out = tmp_path / "data.json"
    result = runner.invoke(
        app, ["eval-detector", "--data", str(supplied / "detector.yaml"), "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["label"] == "measured on the supplied set"
    assert payload["set"] == {}
    assert payload["counts"]["images"] == 0

    missing = runner.invoke(app, ["eval-detector", "--data", str(tmp_path / "none.yaml")])
    assert missing.exit_code != 0


# --- the detector on a list of photos ---------------------------------------------------
def test_a_split_may_be_a_list_of_photos(tmp_path: Path) -> None:
    (tmp_path / "images").mkdir()
    (tmp_path / "list.txt").write_text("images/a.jpg\nimages/b.PNG\n\nnotes.md\n", encoding="utf-8")
    yaml_path = tmp_path / "detector.yaml"
    yaml_path.write_text("val: list.txt\nnames:\n  0: LP\n", encoding="utf-8")
    assert split_images(yaml_path, "val") == 2


def test_the_detector_measurement_keeps_its_note(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Box:
        mp, mr, map50, map = 0.5, 0.75, 0.625, 0.25

    class Metrics:
        box = Box()
        nt_per_class = np.array([2])
        nt_per_image = np.array([2])

    class YOLO:
        def __init__(self, weights: str) -> None:
            pass

        def val(self, **kwargs: Any) -> Metrics:
            return Metrics()

    module = types.ModuleType("ultralytics")
    module.YOLO = YOLO  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ultralytics", module)
    (tmp_path / "images").mkdir()
    yaml_path = tmp_path / "detector.yaml"
    yaml_path.write_text("val: images\nnames:\n  0: LP\n", encoding="utf-8")
    payload = evaluate_detector(yaml_path, Path("best.pt"), synthetic=False, note="  photos  ")
    assert payload["note"] == "photos"
    assert payload["label"] == "measured on the supplied set"
    out = tmp_path / "result.json"
    result = CliRunner().invoke(
        app,
        ["eval-detector", "--data", str(yaml_path), "--out", str(out), "--note", "street photos"],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(out.read_text(encoding="utf-8"))["note"] == "street photos"
