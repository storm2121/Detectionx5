"""The detector's Ultralytics paths on a tiny synthetic scene set: validation and training.

Both run real Ultralytics code on CPU, so they are opt-in like the real-model API test:
set ``PLATE_TEST_MODELS=1``. The committed results come from ``plate eval-detector`` on a
larger synthetic set and are rendered in the README.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from plate_reader.synthetic import write_scenes

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "models" / "best.pt"
RUN = os.environ.get("PLATE_TEST_MODELS") == "1" and WEIGHTS.exists()


@pytest.mark.skipif(not RUN, reason="set PLATE_TEST_MODELS=1 to run Ultralytics on CPU")
def test_validation_reports_map_on_synthetic_scenes(tmp_path: Path) -> None:
    from plate_reader.eval.detector import evaluate_detector

    write_scenes(tmp_path / "scenes", 12, 1005, val_fraction=0.5)
    payload = evaluate_detector(
        tmp_path / "scenes" / "detector.yaml",
        WEIGHTS,
        imgsz=320,
        batch=4,
        device="cpu",
        project=tmp_path / "runs",
    )
    metrics = payload["metrics"]
    assert set(metrics) == {"precision", "recall", "map50", "map50_95"}
    assert all(0.0 <= v <= 1.0 for v in metrics.values())
    assert payload["set"]["seed"] == 1005
    assert payload["label"] == "synthetic results are not real-world accuracy"


@pytest.mark.skipif(not RUN, reason="set PLATE_TEST_MODELS=1 to run Ultralytics on CPU")
def test_training_runs_end_to_end_on_synthetic_scenes(tmp_path: Path) -> None:
    from plate_reader.training.train_detector import train_detector

    write_scenes(tmp_path / "scenes", 8, 1001, val_fraction=0.5)
    summary = train_detector(
        tmp_path / "scenes" / "detector.yaml",
        epochs=1,
        imgsz=160,
        batch=4,
        workers=0,
        weights=str(WEIGHTS),
        project=tmp_path / "runs",
        device="cpu",
        amp=False,
        results_dir=tmp_path / "results",
    )
    assert Path(summary["weights"]).exists()
    rows = (tmp_path / "results" / "detector_training.csv").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 2  # the header and one epoch
    assert json.dumps(summary)
