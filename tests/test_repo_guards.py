"""Repository guards (AGENT_RULES §1.1 and §1.2), run in CI as ordinary tests."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import repo_guards
from repo_guards import ForbiddenToken, check_data, check_names, find_forbidden


def token_for(word: str) -> ForbiddenToken:
    """A stand-in forbidden token, so the test never needs the real names."""
    normalised = repo_guards.normalise(word)
    return ForbiddenToken(len(normalised), hashlib.sha256(normalised.encode()).hexdigest(), "test")


def test_repository_never_mentions_the_dataset_host_or_name() -> None:
    files = repo_guards.repository_files(ROOT)
    assert files, "git ls-files returned nothing"
    assert check_names(files) == []


def test_repository_holds_no_real_data() -> None:
    assert check_data(repo_guards.repository_files(ROOT)) == []


@pytest.mark.parametrize(
    "text",
    [
        "trained on zebracorn data",
        "see https://universe.ZebraCorn.com/ws/project",
        "Zebra-Corn",
        "z e b r a c o r n",
        "ＺＥＢＲＡＣＯＲＮ",  # full-width forms
    ],
)
def test_spellings_that_must_be_caught(text: str) -> None:
    token = token_for("zebracorn")
    assert find_forbidden(text, (token,)) == [token]


def test_unrelated_text_passes() -> None:
    assert find_forbidden("a zebra eats corn", (token_for("zebracorn"),)) == []
    assert find_forbidden("short", (token_for("zebracorn"),)) == []


def test_files_are_scanned_and_binaries_skipped(tmp_path: Path) -> None:
    token = token_for("zebracorn")
    (tmp_path / "doc.md").write_text("Credits: ZebraCorn", encoding="utf-8")
    (tmp_path / "weights.pt").write_bytes(b"zebracorn")
    (tmp_path / "blob.bin").write_bytes(b"\0zebracorn")
    problems = check_names(sorted(tmp_path.iterdir()), (token,))
    assert problems == [f"{tmp_path / 'doc.md'}: mentions the forbidden test"]


def test_data_guard_rejects_images_and_large_csvs(tmp_path: Path) -> None:
    data = tmp_path / "data" / "ocr" / "train"
    data.mkdir(parents=True)
    (data / "crop.png").write_bytes(b"png")
    (data / "small.csv").write_text("a\n" + "x\n" * 50, encoding="utf-8")
    (data / "labels.csv").write_text("a\n" + "x\n" * 51, encoding="utf-8")
    (data / "README.md").write_text("fine", encoding="utf-8")
    outside = tmp_path / "samples"
    outside.mkdir()
    (outside / "car.jpg").write_bytes(b"jpg")
    problems = check_data(
        [
            data / "crop.png",
            data / "small.csv",
            data / "labels.csv",
            data / "README.md",
            outside / "car.jpg",
        ],
        root=tmp_path,
    )
    assert len(problems) == 2
    assert "crop.png" in problems[0]
    assert "more than 50 rows" in problems[1]


def test_command_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    clean = tmp_path / "clean.md"
    clean.write_text("nothing to see", encoding="utf-8")
    assert repo_guards.main(["names", str(clean)]) == 0
    assert repo_guards.main(["names", "--commit-msg", str(clean)]) == 0
    assert repo_guards.main(["data", str(clean)]) == 0
