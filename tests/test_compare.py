"""``plate compare-crnn``: the paired comparison that decides whether new CRNN weights ship."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from plate_reader.cli import app
from plate_reader.docs_render import SYNTHETIC_LABEL
from plate_reader.eval.compare import DECIDING_SET, RULE, SCHEMA, compare_crnn

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = ROOT / "models" / "crnn.onnx"


def test_a_model_compared_with_itself_is_never_adopted() -> None:
    payload = compare_crnn(SHIPPED, SHIPPED, n=24, resamples=100)
    assert payload["schema"] == SCHEMA
    assert payload["label"] == SYNTHETIC_LABEL
    assert payload["deciding_set"] == DECIDING_SET == "synthetic"
    assert payload["rule"] == RULE
    assert payload["old"]["version"] == payload["new"]["version"]
    assert payload["bootstrap"]["paired"] is True
    assert set(payload["sets"]) == {"synthetic", "pseudo_real"}
    for entry in payload["sets"].values():
        assert entry["old"] == entry["new"]
        assert entry["difference"]["value"] == 0.0
        assert entry["difference"]["ci_low"] == entry["difference"]["ci_high"] == 0.0
        assert entry["only_old_right"] == entry["only_new_right"] == 0
        assert entry["set"]["n"] == 24
    assert payload["adopt"] is False


def test_cli_writes_the_comparison_and_the_verdict(tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "comparison.json"
    args = ["compare-crnn", "--old", str(SHIPPED), "--new", str(SHIPPED), "--n", "20"]
    result = runner.invoke(app, [*args, "--resamples", "100", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert "keep the old weights" in result.output
    assert SYNTHETIC_LABEL in result.output
    assert json.loads(out.read_text(encoding="utf-8"))["adopt"] is False
    summary = tmp_path / "train_crnn.json"
    summary.write_text(
        json.dumps(
            {
                "config": {"epochs": 24, "epoch_size": 20000},
                "seconds": 1.5,
                "best_epoch": 18,
                "best_val_exact_greedy": 0.995,
                "augment_source": {"file": "results/sweep.json", "trial": 5},
            }
        ),
        encoding="utf-8",
    )
    result = runner.invoke(
        app, [*args, "--resamples", "100", "--out", str(out), "--new-summary", str(summary)]
    )
    assert result.exit_code == 0, result.output
    training = json.loads(out.read_text(encoding="utf-8"))["new"]["training"]
    assert training["augment_source"]["trial"] == 5
    assert training["epochs"] == 24
    missing = runner.invoke(
        app, ["compare-crnn", "--old", str(tmp_path / "x.onnx"), "--new", str(SHIPPED)]
    )
    assert missing.exit_code != 0
