"""The render step: numbers come from sources, and hand-typed numbers fail the check."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

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
