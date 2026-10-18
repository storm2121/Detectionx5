"""IoU tracking, Alembic migrations, the model registry and the ONNX detector."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy import create_engine, inspect
from typer.testing import CliRunner

from plate_reader.cli import app
from plate_reader.crnn.runtime import file_version
from plate_reader.detector import Detection
from plate_reader.detector_onnx import letterbox
from plate_reader.training.registry import data_fingerprint, find_model, listing, promote
from services.api.db import alembic_config, migrate
from services.api.tracking import IoUTracker

ROOT = Path(__file__).resolve().parents[1]


def det(x: int, y: int, w: int = 60, h: int = 20, conf: float = 0.9) -> Detection:
    return Detection((x, y, x + w, y + h), conf, np.zeros((h, w, 3), dtype=np.uint8))


# --- tracking -----------------------------------------------------------------------
def test_a_drifting_plate_is_one_track_and_two_plates_are_two() -> None:
    tracker = IoUTracker()
    for frame in range(10):
        tracker.update(frame, [det(10 + 3 * frame, 50), det(200, 10 + 2 * frame)])
    tracks = tracker.finish()
    assert len(tracks) == 2
    assert all(len(t.observations) == 10 for t in tracks)


def test_tracks_close_after_misses_and_new_tracks_start() -> None:
    tracker = IoUTracker(max_misses=1)
    tracker.update(0, [det(10, 10)])
    tracker.update(1, [])
    tracker.update(2, [])
    assert tracker.open_tracks == []
    tracker.update(3, [det(10, 10)])
    assert len(tracker.finish()) == 2


@given(
    st.lists(
        st.lists(st.tuples(st.integers(0, 400), st.integers(0, 300)), max_size=4),
        min_size=1,
        max_size=8,
    )
)
def test_every_detection_lands_in_exactly_one_track(frames: list[list[tuple[int, int]]]) -> None:
    tracker = IoUTracker()
    total = 0
    for index, boxes in enumerate(frames):
        tracker.update(index, [det(x, y) for x, y in boxes])
        total += len(boxes)
    tracks = tracker.finish()
    assert sum(len(t.observations) for t in tracks) == total
    for track in tracks:
        assert len(set(track.frames)) == len(track.frames)  # one detection per frame per track
        assert track.frames == sorted(track.frames)


# --- migrations ----------------------------------------------------------------------
def test_migrations_create_and_drop_the_schema(tmp_path: Path) -> None:
    from alembic import command

    # The folder does not exist yet: a first local run must still create the database.
    url = f"sqlite:///{(tmp_path / 'fresh' / 'm.db').as_posix()}"
    migrate(url)
    tables = set(inspect(create_engine(url)).get_table_names())
    assert {"reads", "read_views", "review_items", "jobs", "exports", "alembic_version"} <= tables
    command.downgrade(alembic_config(url), "base")
    assert set(inspect(create_engine(url)).get_table_names()) == {"alembic_version"}


# --- registry -------------------------------------------------------------------------
def test_promote_records_metrics_fingerprint_and_activates(tmp_path: Path) -> None:
    models = tmp_path / "models"
    models.mkdir()
    (models / "crnn.onnx").write_bytes(b"onnx bytes")
    version = file_version(models / "crnn.onnx")
    results = tmp_path / "results"
    results.mkdir()
    payload = {
        "set": {"kind": "synthetic"},
        "recognizers": {
            "crnn-beam": {
                "model_version": f"crnn-{version}-T0.9",
                "n": 10,
                "metrics": {"exact_match": {"value": 0.9}},
            },
            "easyocr": {"model_version": "easyocr", "metrics": {}},
        },
    }
    (results / "eval_synthetic.json").write_text(json.dumps(payload), encoding="utf-8")
    (results / "calibration_crnn.json").write_text(
        json.dumps(
            {
                "model_version": version,
                "conformal": {"coverage": {"0.1": {"coverage": {"value": 0.9}}}},
            }
        ),
        encoding="utf-8",
    )
    entry = promote(version, models, results, tmp_path / "data")
    assert entry["kind"] == "crnn"
    assert entry["metrics"]["eval_synthetic/crnn-beam"]["set_kind"] == "synthetic"
    assert "eval_synthetic/easyocr" not in entry["metrics"]
    assert entry["metrics"]["calibration_crnn"]["coverage"]["0.1"]["value"] == 0.9
    assert entry["data_fingerprint"].startswith("synthetic:")
    registry = listing(models / "registry.json")
    assert registry["active"] == {"crnn": version}
    promote(version, models, results, tmp_path / "data")
    assert len(listing(models / "registry.json")["models"]) == 1
    with pytest.raises(KeyError):
        find_model("000000000000", models)

    labels = tmp_path / "data" / "ocr" / "train" / "labels.csv"
    labels.parent.mkdir(parents=True)
    labels.write_text("crop_path,plate_text,format\n", encoding="utf-8")
    assert data_fingerprint(tmp_path / "data").startswith("data:")


def test_registry_cli(tmp_path: Path) -> None:
    models = tmp_path / "models"
    models.mkdir()
    (models / "crnn.onnx").write_bytes(b"x")
    runner = CliRunner()
    version = file_version(models / "crnn.onnx")
    assert (
        runner.invoke(app, ["registry", "promote", version, "--models-dir", str(models)]).exit_code
        == 0
    )
    listed = runner.invoke(app, ["registry", "list", "--models-dir", str(models)])
    assert version in listed.output
    assert (
        runner.invoke(app, ["registry", "promote", "nope", "--models-dir", str(models)]).exit_code
        == 1
    )


# --- ONNX detector ---------------------------------------------------------------------
def test_letterbox_keeps_aspect_and_centres() -> None:
    image = np.zeros((100, 300, 3), dtype=np.uint8)
    padded, scale, (left, top) = letterbox(image, 640)
    assert padded.shape == (640, 640, 3)
    assert scale == pytest.approx(640 / 300)
    assert left == 0
    assert top == pytest.approx((640 - round(100 * scale)) / 2, abs=1)


@pytest.mark.skipif(not (ROOT / "models" / "detector.onnx").exists(), reason="no exported detector")
def test_onnx_detector_matches_the_pytorch_detector() -> None:
    pytest.importorskip("ultralytics")
    from plate_reader.detector import PlateDetector, iou
    from plate_reader.detector_onnx import OnnxPlateDetector

    sample = ROOT / "samples" / "car.jpg"
    torch_dets = PlateDetector().detect(sample)
    onnx_dets = OnnxPlateDetector(ROOT / "models" / "detector.onnx").detect(sample)
    assert len(onnx_dets) == len(torch_dets) >= 1
    for a, b in zip(torch_dets, onnx_dets, strict=True):
        assert iou(a.box, b.box) > 0.95
        assert abs(a.confidence - b.confidence) < 0.02


def test_auto_letterbox_pads_only_to_the_stride() -> None:
    image = np.zeros((100, 300, 3), dtype=np.uint8)
    padded, _, (left, top) = letterbox(image, 640, auto=True)
    assert padded.shape[1] == 640
    assert padded.shape[0] % 32 == 0
    assert padded.shape[0] < 640
    assert left == 0
    assert top >= 0
