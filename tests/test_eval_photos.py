"""Labelled photos without a box: the harness must crop exactly what the service crops."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import cv2
import numpy as np
import pytest

from plate_reader.cli import evaluate
from plate_reader.detector import Detection, detections_from_boxes, pad_box
from plate_reader.eval import sets
from plate_reader.settings import PROJECT_ROOT
from plate_reader.synthetic import write_scenes

# A raw detector box whose padding differs by a pixel when it is rounded first.
RAW_BOX = [10.6, 20.4, 50.2, 40.9]


class FakeOnnxDetector:
    """Stands in for OnnxPlateDetector: the real padding, cropping and de-duplication."""

    def __init__(self, model_path: Path | str, confidence: float | None = None) -> None:
        self.model_path = Path(model_path)

    def detect_image(self, image: Any) -> list[Detection]:
        return detections_from_boxes(image, [RAW_BOX, [0.0, 0.0, 8.0, 6.0]], [0.8, 0.3])


def test_no_detector_without_a_model(tmp_path: Path) -> None:
    settings = SimpleNamespace(detector_model=tmp_path / "missing.onnx")
    assert evaluate._detector_for_photos(settings) is None


def test_the_detector_returns_the_served_crop_boxes_as_ints(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = tmp_path / "detector.onnx"
    model.write_bytes(b"not a real model")
    monkeypatch.setattr("plate_reader.detector_onnx.OnnxPlateDetector", FakeOnnxDetector)
    detect = evaluate._detector_for_photos(SimpleNamespace(detector_model=model))
    assert detect is not None
    image = np.zeros((60, 100, 3), dtype=np.uint8)
    found = detect(image)
    assert [score for _, score in found] == [0.8, 0.3]
    for box, _ in found:
        assert all(type(v) is int for v in box)
    # The float box padded once, as the service pads it, not a box rounded before padding.
    assert found[0][0] == pad_box(RAW_BOX, 100, 60)
    assert found[0][0] != pad_box([float(int(v)) for v in RAW_BOX], 100, 60)


def test_a_photo_without_a_box_is_cut_where_the_service_cuts_it(tmp_path: Path) -> None:
    write_scenes(tmp_path / "scenes", 3, seed=11)
    labels = tmp_path / "scenes" / "eval" / "labels.csv"
    lines = labels.read_text(encoding="utf-8").splitlines()
    stripped = [lines[0]] + [",".join([*line.split(",")[:3], "", "", "", ""]) for line in lines[1:]]
    labels.write_text("\n".join(stripped) + "\n", encoding="utf-8")
    fake = FakeOnnxDetector("unused")

    def detect(image: Any) -> list[tuple[tuple[int, int, int, int], float]]:
        return [(d.box, d.confidence) for d in fake.detect_image(image)]

    data = sets.data_set(tmp_path / "scenes", detect=detect)
    assert len(data.items) == len(stripped) - 1
    for item, line in zip(data.items, stripped[1:], strict=True):
        photo = cv2.imread(str(labels.parent / line.split(",")[0]), cv2.IMREAD_COLOR)
        served = max(fake.detect_image(photo), key=lambda d: d.confidence)
        assert np.array_equal(item.image, served.crop)
        assert item.meta == {"box": "detector", "detector_confidence": 0.8}


def test_results_record_repository_relative_sources(tmp_path: Path) -> None:
    inside = PROJECT_ROOT / "data" / "eval" / "labels.csv"
    assert sets.repository_path(inside) == "data/eval/labels.csv"
    outside = Path(tmp_path.anchor) / "elsewhere" / "eval" / "labels.csv"
    if PROJECT_ROOT in outside.resolve().parents:  # pragma: no cover - unusual checkout
        pytest.skip("the repository is the filesystem root")
    assert sets.repository_path(outside) == "<outside the repository>/eval/labels.csv"


def test_the_cli_records_the_note_and_a_relative_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import json

    from typer.testing import CliRunner

    from plate_reader.cli import app
    from plate_reader.eval import recognizers
    from plate_reader.hypotheses import ViewRead

    class Blank:
        name = "blank"
        version = "blank-1"

        def read(self, image: Any) -> ViewRead:
            return ViewRead()

    monkeypatch.setitem(recognizers.REGISTRY, "blank", lambda **_: Blank())
    monkeypatch.setattr(evaluate, "_detector_for_photos", lambda settings: None)
    write_scenes(tmp_path / "scenes", 3, seed=12)
    result = CliRunner().invoke(
        app,
        [
            "eval",
            "--set",
            "data",
            "--data-dir",
            str(tmp_path / "scenes"),
            "-r",
            "blank",
            "--views",
            "0",
            "--resamples",
            "100",
            "--out",
            str(tmp_path / "out"),
            "--quiet",
            "--note",
            "small and easy (generated scenes)",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(
        (tmp_path / "out" / "eval_data_synthetic.json").read_text(encoding="utf-8")
    )
    assert payload["set"]["note"] == "small and easy (generated scenes)"
    assert not Path(payload["set"]["source"]).is_absolute()
    assert payload["set"]["source"].endswith("eval/labels.csv")
