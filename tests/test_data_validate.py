"""The real-data validator, exercised on synthetic fixtures only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

from plate_reader.cli import app
from plate_reader.data import DataLayout, validate_data

ROOT = Path(__file__).resolve().parents[1]


def _png(path: Path, size: tuple[int, int] = (64, 32)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "white").save(path)


@pytest.fixture
def layout(tmp_path: Path) -> DataLayout:
    layout = DataLayout(tmp_path / "data")
    for directory in layout.directories():
        directory.mkdir(parents=True, exist_ok=True)
    return layout


def _tracked_data_files() -> list[str]:
    import shutil
    import subprocess

    git = shutil.which("git")
    if git is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    listed = subprocess.run(
        [git, "ls-files", "data"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [line for line in listed.stdout.splitlines() if line]


def test_repository_placeholder_is_valid_and_empty(tmp_path: Path) -> None:
    """What the repository ships under data/ is the empty placeholder, whatever is local.

    Real photos may sit in a working copy (they are gitignored); the committed files, laid
    out on their own, must still be the valid, empty layout, and the local folder must
    validate too.
    """
    tracked = _tracked_data_files()
    assert tracked
    allowed = {"README.md", "detector.yaml", ".gitkeep"}
    assert all(Path(name).name in allowed for name in tracked), tracked
    for name in tracked:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    report = validate_data(tmp_path / "data")
    assert report.ok(strict=True)
    assert report.is_empty
    assert validate_data(ROOT / "data").ok()


def test_missing_folder_is_an_error(tmp_path: Path) -> None:
    report = validate_data(tmp_path / "absent")
    assert not report.ok()


def test_valid_data_passes(layout: DataLayout) -> None:
    _png(layout.detector_images("train") / "a.png", (100, 50))
    layout.detector_labels("train").joinpath("a.txt").write_text("0 0.5 0.5 0.2 0.1\n")
    layout.detector_yaml.write_text(
        "train: detector/images/train\nval: detector/images/val\nnames:\n  0: LP\n"
    )
    _png(layout.ocr_labels("train").parent / "crops" / "c1.png")
    layout.ocr_labels("train").write_text(
        "crop_path,plate_text,format\ncrops/c1.png,24830-ب-1,standard\n", encoding="utf-8"
    )
    _png(layout.eval_labels.parent / "photos" / "p1.png", (200, 100))
    layout.eval_labels.write_text(
        "image_path,plate_text,format,x1,y1,x2,y2\n"
        "photos/p1.png,72173 WW,temporary,10,10,90,40\n"
        "photos/p1.png,24830-ب-1,standard,,,,\n",
        encoding="utf-8",
    )
    report = validate_data(layout.root)
    assert report.errors == []
    assert report.counts["detector_train_boxes"] == 1
    assert report.counts["ocr_train_crops"] == 1
    # two plates in one photo: photos and plates are counted apart
    assert report.counts["eval_images"] == 1
    assert report.counts["eval_plates"] == 2


def test_the_eval_csv_may_name_groups_and_carry_a_card(layout: DataLayout) -> None:
    _png(layout.eval_labels.parent / "photos" / "p1.png", (200, 100))
    _png(layout.eval_labels.parent / "photos" / "p2.png", (200, 100))
    layout.eval_labels.write_text(
        "image_path,plate_text,format,x1,y1,x2,y2,group\n"
        "photos/p1.png,72173 WW,temporary,10,10,90,40,g1\n"
        "photos/p2.png,72173 WW,temporary,10,10,90,40,g1\n",
        encoding="utf-8",
    )
    layout.eval_card.write_text('{"description": "two photos of one car"}', encoding="utf-8")
    report = validate_data(layout.root)
    assert report.errors == []
    assert report.counts["eval_images"] == 2

    layout.eval_labels.write_text(
        "image_path,plate_text,format,x1,y1,x2,y2,group\n"
        "photos/p1.png,72173 WW,temporary,10,10,90,40,\n",
        encoding="utf-8",
    )
    layout.eval_card.write_text("[1, 2]", encoding="utf-8")
    messages = " | ".join(i.message for i in validate_data(layout.root).errors)
    assert "group is empty" in messages
    assert "must be a JSON object" in messages

    layout.eval_labels.write_text(
        "image_path,plate_text,format,x1,y1,x2,y2,vehicle\n"
        "photos/p1.png,72173 WW,temporary,10,10,90,40,a\n",
        encoding="utf-8",
    )
    layout.eval_card.write_text("{not json", encoding="utf-8")
    messages = " | ".join(i.message for i in validate_data(layout.root).errors)
    assert "header must be image_path,plate_text,format,x1,y1,x2,y2[,group]" in messages
    assert "invalid JSON" in messages


def test_label_problems_are_errors(layout: DataLayout) -> None:
    labels = layout.detector_labels("val")
    labels.joinpath("orphan.txt").write_text("0 0.5 0.5 0.2 0.1\n")
    _png(layout.detector_images("val") / "b.png")
    labels.joinpath("b.txt").write_text("1 0.5 0.5 0.2 0.1\n0 1.5 0.5 0.2 0.1\n0 x\n0 a b c d\n")
    _png(layout.detector_images("val") / "background.png")
    _png(layout.ocr_labels("val").parent / "c.png")
    layout.ocr_labels("val").write_text(
        "crop_path,plate_text,format\n"
        "c.png,24830-ز-1,standard\n"  # letter not on any plate
        "c.png,72173 WW,standard\n"  # duplicate crop and wrong format
        "missing.png,24830 ب 1,standard\n"  # missing crop, non-canonical spelling
        "c.png,1 WW,diplomatic\n",
        encoding="utf-8",
    )
    layout.eval_labels.write_text(
        "image_path,plate_text,format,x1,y1,x2,y2\n"
        "nope.png,24830-ب-1,standard,1,2,,\n"
        "nope.png,24830-ب-1,standard,a,b,c,d\n"
        "nope.png,24830-ب-1,standard,9,9,1,1\n",
        encoding="utf-8",
    )
    report = validate_data(layout.root)
    messages = " | ".join(i.message for i in report.errors)
    for fragment in (
        "label file without a matching image",
        "class 1 out of range",
        "normalised",
        "five fields",
        "non-numeric",
        "not a valid plate",
        "duplicate crop_path",
        "contradicts",
        "does not exist",
        "must be one of",
        "all of x1,y1,x2,y2",
        "integers",
        "0 <= x1 < x2",
        "missing: detector images exist without detector.yaml",
    ):
        assert fragment in messages, fragment
    warnings = " | ".join(i.message for i in report.warnings)
    assert "background" in warnings
    assert "not canonical" in warnings


def test_bad_headers_yaml_and_boxes(layout: DataLayout) -> None:
    layout.ocr_labels("train").write_text("path,text\nx,y\n", encoding="utf-8")
    layout.detector_yaml.write_text("names: [car, LP]\n")
    _png(layout.eval_labels.parent / "p.png", (50, 50))
    layout.eval_labels.write_text(
        "image_path,plate_text,format,x1,y1,x2,y2\np.png,24830-ب-1,standard,1,1,60,40\n",
        encoding="utf-8",
    )
    corrupt = layout.ocr_labels("val").parent / "bad.png"
    corrupt.write_bytes(b"not an image")
    layout.ocr_labels("val").write_text(
        "crop_path,plate_text,format\nbad.png,24830-ب-1,standard\n", encoding="utf-8"
    )
    messages = " | ".join(i.message for i in validate_data(layout.root).errors)
    assert "header must be" in messages
    assert "names must be" in messages
    assert "exceeds the image" in messages
    assert "cannot be decoded" in messages

    layout.detector_yaml.write_text("names: [unclosed\n")
    assert any("invalid YAML" in i.message for i in validate_data(layout.root).errors)


def test_cli_reports(layout: DataLayout) -> None:
    runner = CliRunner()
    empty = runner.invoke(app, ["data", "validate", "--root", str(layout.root)])
    assert empty.exit_code == 0
    assert "empty placeholder" in empty.output
    _png(layout.detector_images("train") / "lonely.png")
    strict = runner.invoke(app, ["data", "validate", "--root", str(layout.root), "--strict"])
    assert strict.exit_code == 1
    as_json = runner.invoke(app, ["data", "validate", "--root", str(layout.root), "--json"])
    assert json.loads(as_json.output)["warnings"]
    fresh = layout.root.parent / "fresh"
    assert runner.invoke(app, ["data", "init", "--root", str(fresh)]).exit_code == 0
    assert (fresh / "ocr" / "train").is_dir()
