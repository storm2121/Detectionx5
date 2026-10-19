"""The render step: numbers come from sources, and hand-typed numbers fail the check."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from plate_reader.cli import app
from plate_reader.docs_render import (
    NO_REAL_BENCHMARK,
    SYNTHETIC_LABEL,
    RenderContext,
    best_detector_epoch,
    check_files,
    check_text,
    find_hand_typed,
    render_files,
    render_text,
)

ROOT = Path(__file__).resolve().parents[1]

TEMPLATE = """# Project

Prose without metrics, a version `0.25` in code, and a port 8100.

<!-- BEGIN RENDER detector-metrics -->
<!-- END RENDER detector-metrics -->

- <!-- BEGIN RENDER ocr-benchmark-status -->
<!-- END RENDER ocr-benchmark-status -->

<!-- BEGIN RENDER synthetic-baseline -->
<!-- END RENDER synthetic-baseline -->

```json
{"confidence": 0.875}
```
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    shutil.copy(ROOT / "docs" / "training_results.csv", tmp_path / "docs")
    (tmp_path / "models").mkdir()
    shutil.copy(ROOT / "models" / "best.pt", tmp_path / "models")
    (tmp_path / "README.md").write_text(TEMPLATE, encoding="utf-8")
    assert render_files(tmp_path) == []
    return tmp_path


def test_detector_block_renders_the_shipped_epoch(repo: Path) -> None:
    ctx = RenderContext(root=repo)
    row = best_detector_epoch(ctx)
    assert int(row["epoch"]) == 90  # the checkpoint shipped as models/best.pt
    text = (repo / "README.md").read_text(encoding="utf-8")
    for value in ("0.956", "0.945", "0.983", "0.744"):
        assert f"| {value} |" in text
    # The wrong final-epoch numbers the old README showed must not come back.
    for wrong in ("0.958", "0.957", "0.987", "0.743"):
        assert wrong not in text


def test_rendered_file_passes_the_check(repo: Path) -> None:
    assert check_files(repo) == []
    text = (repo / "README.md").read_text(encoding="utf-8")
    assert NO_REAL_BENCHMARK in text
    assert SYNTHETIC_LABEL.capitalize() in text


def test_a_hand_edited_number_inside_a_block_fails(repo: Path) -> None:
    readme = repo / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace("| 0.956 |", "| 0.961 |"), encoding="utf-8"
    )
    problems = check_files(repo)
    assert any("drifted" in p.message for p in problems)


def test_a_hand_typed_number_in_prose_fails(repo: Path) -> None:
    readme = repo / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8") + "\nOur reader reaches 0.97 exact match.\n",
        encoding="utf-8",
    )
    problems = check_files(repo)
    assert [p.message for p in problems] == ["hand-typed metric-like number '0.97' outside a block"]


@pytest.mark.parametrize("prose", ["accuracy of 97%", "a 99.5 % hit rate", "recall 1.000"])
def test_percentages_and_decimals_are_detected(prose: str) -> None:
    assert find_hand_typed(prose)


def test_numbers_in_code_comments_and_blocks_are_not_flagged() -> None:
    text = "Use `--conf 0.40`.\n<!-- 0.99 -->\n```\nscore 0.993\n```\nport 8100, 2 photos.\n"
    assert find_hand_typed(text) == []


def test_drift_after_new_results_is_detected(repo: Path) -> None:
    results = repo / "results"
    results.mkdir()
    payload = {
        "set": {"kind": "synthetic", "name": "crops", "n": 10, "seed": 1},
        "bootstrap": {"resamples": 1000},
        "recognizers": {
            "easyocr": {"metrics": {"exact_match": {"value": 0.5, "ci_low": 0.2, "ci_high": 0.8}}}
        },
    }
    (results / "eval_synthetic.json").write_text(json.dumps(payload), encoding="utf-8")
    assert any("drifted" in p.message for p in check_files(repo))
    assert render_files(repo) == []
    assert check_files(repo) == []
    assert "0.500 [0.200, 0.800]" in (repo / "README.md").read_text(encoding="utf-8")


def test_honesty_statements_are_enforced(repo: Path) -> None:
    ctx = RenderContext(root=repo)
    rendered, _ = render_text(TEMPLATE, ctx, "README.md")
    stripped = rendered.replace(NO_REAL_BENCHMARK, "Accuracy is great")
    stripped = stripped.replace(SYNTHETIC_LABEL.capitalize(), "Numbers")
    messages = [p.message for p in check_text(stripped, ctx, "README.md")]
    assert any("must stay" in m for m in messages)
    assert any("without the sentence" in m for m in messages)


def test_unknown_and_unclosed_blocks_are_reported(repo: Path) -> None:
    ctx = RenderContext(root=repo)
    text = "<!-- BEGIN RENDER nope -->\n<!-- END RENDER nope -->\n<!-- BEGIN RENDER x -->\n"
    messages = [p.message for p in check_text(text, ctx, "doc.md")]
    assert "unknown render block 'nope'" in messages
    assert "block 'x' is not closed" in messages


def test_training_log_parses_every_epoch() -> None:
    with (ROOT / "docs" / "training_results.csv").open(encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert len(RenderContext(root=ROOT).training_rows) == len(rows) - 1


def test_repository_docs_are_in_sync() -> None:
    assert [str(p) for p in check_files(ROOT)] == []


def test_cli_check_and_render(repo: Path) -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["docs", "check", "--root", str(repo)]).exit_code == 0
    readme = repo / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\n95% accurate\n", encoding="utf-8")
    result = runner.invoke(app, ["docs", "check", "--root", str(repo)])
    assert result.exit_code == 1
    assert runner.invoke(app, ["docs", "render", "--root", str(repo)]).exit_code == 0


def test_the_sweep_block_renders_from_results(tmp_path: Path) -> None:
    from plate_reader.docs_render import BLOCKS

    ctx = RenderContext(tmp_path)
    assert BLOCKS["augmentation-sweep"](ctx).startswith("Not run yet")
    (tmp_path / "results").mkdir()
    trial = {
        "number": 0,
        "multipliers": {"geometry": 1.0, "blur": 1.0},
        "pseudo_real_exact_greedy": 0.5,
        "synthetic_val_exact_greedy": 0.75,
    }
    better = {**trial, "number": 1, "multipliers": {"geometry": 1.5, "blur": 0.75}}
    better["pseudo_real_exact_greedy"] = 0.625
    payload = {
        "budget": {"epochs": 3, "epoch_size": 4000, "tune_size": 300, "device": "cuda"},
        "splits": {"tuning": {"seed": 1009}},
        "groups": {"geometry": ["perspective"], "blur": ["gaussian_sigma"]},
        "baseline": trial,
        "best": better,
        "trials": [trial, better],
        "adopted": False,
    }
    (tmp_path / "results" / "sweep.json").write_text(json.dumps(payload), encoding="utf-8")
    text = BLOCKS["augmentation-sweep"](RenderContext(tmp_path))
    assert SYNTHETIC_LABEL.capitalize() in text
    rows = [line for line in text.splitlines() if line.startswith("| 0") or line.startswith("| 1")]
    assert rows[0].startswith("| 1 (best) | 1.50 | 0.75 | 0.625")
    assert rows[1].startswith("| 0 (default) | 1.00 | 1.00 | 0.500 | reference")
    assert "keeps the default configuration" in text


def test_the_cv_evidence_block_traces_every_figure_to_a_file(tmp_path: Path) -> None:
    from plate_reader.docs_render import BLOCKS

    assert BLOCKS["cv-evidence"](RenderContext(tmp_path)).startswith("No results yet")
    text = BLOCKS["cv-evidence"](RenderContext(ROOT))
    rows = [line for line in text.splitlines() if line.startswith("| ") and "Claim" not in line]
    assert rows
    assert all(line.rstrip(" |").endswith(".json`") for line in rows)
    assert SYNTHETIC_LABEL.capitalize() in text


def test_the_detector_block_renders_from_its_validation(tmp_path: Path) -> None:
    from plate_reader.docs_render import BLOCKS

    assert BLOCKS["detector-synthetic"](RenderContext(tmp_path)).startswith("Not measured yet")
    (tmp_path / "results").mkdir()
    payload = {
        "weights": "best.pt",
        "data": "synthetic/scenes-eval/detector.yaml",
        "split": "val",
        "imgsz": 640,
        "set": {"seed": 1005, "n": 40, "val_fraction": 0.5, "generator_version": "1"},
        "counts": {"images": 20, "plates": 18, "images_with_plates": 18},
        "metrics": {"precision": 0.75, "recall": 0.875, "map50": 0.8125, "map50_95": 0.5},
    }
    target = tmp_path / "results" / "eval_detector_synthetic.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    text = BLOCKS["detector-synthetic"](RenderContext(tmp_path))
    assert text.startswith(f"**{SYNTHETIC_LABEL.capitalize()}.**")
    assert "20 scenes holding 18 plates (2 with no plate)" in text
    assert "| mAP@50 | 0.812 |" in text
    assert "| mAP@50-95 | 0.500 |" in text
    assert "--n 40 --seed 1005 --val-fraction 0.5 --out synthetic/scenes-eval" in text
    del payload["counts"]
    target.write_text(json.dumps(payload), encoding="utf-8")
    assert "the whole split" in BLOCKS["detector-synthetic"](RenderContext(tmp_path))
    assert "Precision is below recall by 0.125" in text
    payload["metrics"]["precision"] = 0.9
    target.write_text(json.dumps(payload), encoding="utf-8")
    assert "Precision is below recall" not in BLOCKS["detector-synthetic"](RenderContext(tmp_path))


def _estimate(value: float, low: float, high: float) -> dict[str, float]:
    return {"value": value, "ci_low": low, "ci_high": high, "n": 2000}


def test_the_comparison_block_states_the_rule_and_the_outcome(tmp_path: Path) -> None:
    from plate_reader.docs_render import BLOCKS

    assert BLOCKS["crnn-comparison"](RenderContext(tmp_path)).startswith("No comparison yet")
    (tmp_path / "results").mkdir()
    payload = {
        "old": {"version": "crnn-aaa-T1"},
        "new": {
            "version": "crnn-bbb-T1",
            "training": {"epochs": 24, "epoch_size": 20000, "augment_source": {"trial": 5}},
        },
        "bootstrap": {"resamples": 1000, "confidence": 0.95},
        "sets": {
            "synthetic": {
                "set": {"n": 2000},
                "old": _estimate(0.99, 0.985, 0.994),
                "new": _estimate(0.995, 0.992, 0.998),
                "difference": _estimate(0.005, 0.002, 0.008),
                "only_old_right": 3,
                "only_new_right": 13,
            },
            "pseudo_real": {
                "set": {"n": 2000},
                "old": _estimate(0.6, 0.58, 0.62),
                "new": _estimate(0.7, 0.68, 0.72),
                "difference": _estimate(0.1, 0.08, 0.12),
                "only_old_right": 40,
                "only_new_right": 240,
            },
        },
        "rule": "adopt only if the interval lies above zero",
        "adopt": True,
    }
    target = tmp_path / "results" / "crnn_comparison.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    text = BLOCKS["crnn-comparison"](RenderContext(tmp_path))
    assert text.startswith(f"**{SYNTHETIC_LABEL.capitalize()}.**")
    assert "augmentation of sweep trial 5" in text
    assert "| Synthetic test split (decides) | 0.9900 [0.9850, 0.9940] |" in text
    assert "| 0.0050 [0.0020, 0.0080] | 3 | 13 |" in text
    assert "Outcome: the retrained weights replaced the previous ones, which stay" in text
    payload["adopt"] = False
    target.write_text(json.dumps(payload), encoding="utf-8")
    assert "the previous weights stay in service" in BLOCKS["crnn-comparison"](
        RenderContext(tmp_path)
    )


def test_the_training_and_sweep_blocks_follow_the_shipped_augmentation(tmp_path: Path) -> None:
    from plate_reader.docs_render import BLOCKS

    (tmp_path / "results").mkdir()
    trial = {
        "number": 0,
        "multipliers": {"geometry": 1.0},
        "pseudo_real_exact_greedy": 0.5,
        "synthetic_val_exact_greedy": 0.75,
    }
    best = {**trial, "number": 3, "multipliers": {"geometry": 1.5}}
    sweep = {"budget": {}, "groups": {"geometry": []}, "baseline": trial, "best": best}
    sweep["trials"] = [trial, best]
    (tmp_path / "results" / "sweep.json").write_text(json.dumps(sweep), encoding="utf-8")
    summary = {"config": {"epochs": 24, "epoch_size": 20000}, "best_val_exact_greedy": 0.99}
    path = tmp_path / "results" / "train_crnn.json"
    path.write_text(json.dumps(summary), encoding="utf-8")
    assert "Augmentation: the generator's default degradation bounds." in BLOCKS["crnn-training"](
        RenderContext(tmp_path)
    )
    (tmp_path / "results" / "crnn_comparison.json").write_text("{}", encoding="utf-8")
    assert "did not replace them" in BLOCKS["augmentation-sweep"](RenderContext(tmp_path))
    summary["augment_source"] = {"trial": 3, "multipliers": {"geometry": 1.5}}
    path.write_text(json.dumps(summary), encoding="utf-8")
    assert "trial 3 of the augmentation sweep (geometry x1.50)" in BLOCKS["crnn-training"](
        RenderContext(tmp_path)
    )
    assert "a full training with the configuration of trial 3" in BLOCKS["augmentation-sweep"](
        RenderContext(tmp_path)
    )


def _estimate(value: float, low: float, high: float, n: int = 12) -> dict[str, Any]:
    return {"value": value, "ci_low": low, "ci_high": high, "n": n}


def test_the_real_photos_block_leads_with_intervals_the_note_and_the_gap(tmp_path: Path) -> None:
    from plate_reader.docs_render import BLOCKS, RenderContext

    ctx = RenderContext(root=tmp_path)
    assert "No labelled real photos yet" in BLOCKS["real-photos"](ctx)
    assert "not benchmarked on real data" in BLOCKS["ocr-benchmark-status"](ctx)
    metrics = {
        "exact_match": _estimate(0.25, 0.0, 0.5),
        "digits_accuracy": _estimate(0.5, 0.25, 0.75),
        "letter_accuracy": _estimate(0.6364, 0.3333, 0.9091, 11),
        "region_accuracy": _estimate(0.6364, 0.3333, 0.9091, 11),
        "cer": _estimate(0.25, 0.1, 0.43),
        "ece": _estimate(0.47, 0.25, 0.68),
        "coverage": _estimate(0.0, 0.0, 0.0),
    }
    ctx._json_cache["eval_data"] = {
        "set": {
            "n": 12,
            "source": "data/eval/labels.csv",
            "note": "small and easy (clean rear shots)",
        },
        "bootstrap": {"confidence": 0.95, "resamples": 1000},
        "recognizers": {"crnn-beam": {"model_version": "crnn-x", "metrics": metrics}},
    }
    ctx._json_cache["eval_synthetic"] = {
        "set": {"n": 300},
        "recognizers": {"crnn-beam": {"metrics": {"exact_match": _estimate(0.99, 0.98, 1.0, 300)}}},
    }
    status = BLOCKS["ocr-benchmark-status"](ctx)
    assert status.startswith(
        "[OCR accuracy is benchmarked on a labelled real set of 12 images](#real-photos)."
    )
    assert "25% (0 to 50)" in status
    block = BLOCKS["real-photos"](ctx)
    assert "| CRNN, constrained beam | `crnn-x` | 25% (0 to 50) | 50% (25 to 75) |" in block
    assert (
        "Twelve photos give a wide interval, and the set is small and easy (clean rear shots)."
        in block
    )
    assert "scored on the 11 standard plates" in block
    assert "| CRNN, constrained beam | 99% (98 to 100) | 25% (0 to 50) | 74 points lower" in block
    assert "Synthetic results are not real-world accuracy" in block
    assert "hold the true plate for 0% (0 to 0)" in block
