"""The ``plate`` command line and the ``cli.py`` shim, with fake models."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

import cli
import config
from plate_reader import Detection, PlateReading, parse_plate
from plate_reader import detector as detector_module
from plate_reader import ocr as ocr_module
from plate_reader import pipeline as pipeline_module
from plate_reader.cli import app
from plate_reader.pipeline import ImageResult, RunResult
from plate_reader.settings import Settings, get_settings


class FakeDetector:
    def __init__(self, model_path: Path | None = None, confidence: float | None = None) -> None:
        if model_path is not None and not Path(model_path).exists():
            raise FileNotFoundError(f"Model weights not found at {model_path}.")


def _result(paths: list[Path], text: str | None) -> RunResult:
    crop = np.full((16, 32, 3), 255, dtype=np.uint8)
    plate = parse_plate(text) if text else None
    readings = [
        PlateReading(
            plate=plate,
            detection=Detection((0, 0, 32, 16), 0.9, crop),
            votes={plate.text: 1.0} if plate else {},
            segmented=True,
        )
    ]
    images = [ImageResult(path=Path(p), readings=list(readings)) for p in paths]
    return RunResult(images=images, plate=plate, votes={plate.text: 1.0} if plate else {})


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> dict[str, str | None]:
    answer: dict[str, str | None] = {"text": "24830-ب-1"}
    monkeypatch.setattr(detector_module, "PlateDetector", FakeDetector)
    monkeypatch.setattr(ocr_module, "get_backend", lambda name="easyocr": object())

    def fake_read(paths: list[Path], **_: object) -> RunResult:
        progress = _.get("progress")
        if callable(progress):
            progress("reading")
        return _result([Path(p) for p in paths], answer["text"])

    monkeypatch.setattr(pipeline_module, "read_images", fake_read)
    return answer


@pytest.fixture
def photo(tmp_path: Path) -> Path:
    path = tmp_path / "car.jpg"
    path.write_bytes(b"not decoded by the fake detector")
    return path


def test_shim_json_output_and_exit_codes(
    fakes: dict[str, str | None], photo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main([str(photo), str(photo), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["plate"] == "24830-ب-1"
    assert payload["found"] is True
    assert payload["images_agreeing"] == 2
    assert payload["images"][0]["plates"][0]["method"] == "fields"

    fakes["text"] = None
    assert cli.main([str(photo), "--quiet"]) == 1
    assert "Plate: unreadable" in capsys.readouterr().out


def test_shim_reports_agreement_and_saves_crops(
    fakes: dict[str, str | None],
    photo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("PLATE_OUTPUT_DIR", str(tmp_path / "crops"))
    get_settings.cache_clear()
    try:
        assert cli.main([str(photo), str(photo), "--save-crops"]) == 0
    finally:
        get_settings.cache_clear()
    out = capsys.readouterr().out
    assert "Agreement: 2/2 images" in out
    assert len(list((tmp_path / "crops").glob("*.jpg"))) == 2


def test_missing_inputs_exit_with_two(fakes: dict[str, str | None], tmp_path: Path) -> None:
    assert cli.main([str(tmp_path / "absent.jpg")]) == 2
    photo = tmp_path / "x.jpg"
    photo.write_bytes(b"x")
    assert cli.main([str(photo), "--model", str(tmp_path / "missing.pt")]) == 2


def test_plate_read_command(fakes: dict[str, str | None], photo: Path) -> None:
    result = CliRunner().invoke(app, ["read", str(photo), "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["plate"] == "24830-ب-1"


def test_plate_help_and_version() -> None:
    runner = CliRunner()
    assert "read" in runner.invoke(app, ["--help"]).output
    assert runner.invoke(app, ["version"]).exit_code == 0


def test_settings_read_the_historical_environment_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PLATE_MODEL", str(tmp_path / "w.pt"))
    monkeypatch.setenv("PLATE_CONF", "0.4")
    monkeypatch.setenv("PLATE_GPU", "1")
    settings = Settings()
    assert settings.model == (tmp_path / "w.pt").resolve()
    assert settings.conf == pytest.approx(0.4)
    assert settings.gpu is True
    monkeypatch.setenv("PLATE_CONF", "2")
    with pytest.raises(ValueError):
        Settings()


def test_config_shim_exposes_the_old_names() -> None:
    assert config.MODEL_PATH.name == "best.pt"
    assert 0 < config.DETECTION_CONF < 1
    assert pytest.approx(0.6) == config.DUPLICATE_IOU
    assert config.SAMPLES_DIR.name == "samples"
