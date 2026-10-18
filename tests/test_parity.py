"""PyTorch versus ONNX Runtime parity (ARCHITECTURE §13)."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import onnx
import pytest
import torch

from plate_reader.crnn.decode import log_softmax, prefix_beam_search
from plate_reader.crnn.model import CRNN
from plate_reader.crnn.preprocess import batch
from plate_reader.crnn.runtime import CRNNRuntime, file_version
from plate_reader.grammar import GRAMMAR
from plate_reader.imaging import as_u8
from plate_reader.synthetic import make_crop
from plate_reader.training.export_onnx import OPSET, export_onnx, write_metadata
from plate_reader.training.train_crnn import load_weights

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models" / "crnn.onnx"
WEIGHTS = ROOT / "models" / "crnn.pt"
FIXTURES = ROOT / "results" / "parity_fixtures.json"
TOLERANCE = 1e-4


def _crops(n: int) -> list[np.ndarray]:
    return [make_crop(2468, i).image for i in range(n)]


def test_export_matches_pytorch_for_any_batch_size(tmp_path: Path) -> None:
    torch.manual_seed(0)
    model = CRNN().eval()
    path = export_onnx(model, tmp_path / "random.onnx")
    graph = onnx.load(str(path))
    assert graph.opset_import[0].version == OPSET
    assert "LSTM" in {node.op_type for node in graph.graph.node}
    write_metadata(path)
    runtime = CRNNRuntime(path)
    for n in (1, 4):
        images = _crops(n)
        expected = model(torch.from_numpy(batch(images))).detach().numpy()
        assert np.abs(runtime.logits(images) - expected).max() < TOLERANCE


@pytest.mark.skipif(not (MODEL.exists() and WEIGHTS.exists()), reason="no committed CRNN yet")
def test_committed_onnx_matches_committed_weights() -> None:
    model = load_weights(WEIGHTS)
    runtime = CRNNRuntime(MODEL)
    assert runtime.version == file_version(MODEL)
    assert MODEL.stat().st_size < 15 * 1024 * 1024
    assert WEIGHTS.stat().st_size < 15 * 1024 * 1024
    images = _crops(8)
    expected = model(torch.from_numpy(batch(images))).detach().numpy()
    actual = runtime.logits(images)
    assert np.abs(actual - expected).max() < TOLERANCE
    t = runtime.metadata.temperature
    for a, e in zip(actual, expected, strict=True):
        lhs = prefix_beam_search(log_softmax(a, t), 10, GRAMMAR)
        rhs = prefix_beam_search(log_softmax(e, t), 10, GRAMMAR)
        assert [h.tokens for h in lhs[:3]] == [h.tokens for h in rhs[:3]]


@pytest.mark.skipif(not FIXTURES.exists(), reason="parity fixtures not written yet")
def test_parity_fixtures_are_reproduced() -> None:
    payload = json.loads(FIXTURES.read_text(encoding="utf-8"))
    runtime = CRNNRuntime(MODEL)
    assert payload["model_version"] == runtime.version
    for fixture in payload["fixtures"]:
        image = as_u8(cv2.imread(str(ROOT / fixture["image"]), cv2.IMREAD_COLOR))
        logits = runtime.logits([image])[0]
        assert np.abs(logits - np.array(fixture["logits"])).max() < payload["tolerance"]["logits"]
        read = runtime.decode(logits, "beam", alpha=payload["alpha"])
        assert read.prediction == fixture["prediction"]
        for (tokens, p), hyp in zip(fixture["beam"], read.hypotheses, strict=True):
            assert hyp.tokens == tokens
            assert abs(hyp.probability - p) < payload["tolerance"]["probability"]
        assert list(read.prediction_set or []) == (fixture["prediction_set"] or [])


DETECTOR = ROOT / "models" / "detector.onnx"


@pytest.mark.skipif(not (MODEL.exists() and DETECTOR.exists()), reason="no committed models")
def test_scene_fixtures_match_the_committed_pipeline() -> None:
    from plate_reader.detector_onnx import OnnxPlateDetector
    from plate_reader.eval.recognizers import CRNNRecognizer
    from plate_reader.pipeline import PlatePipeline

    payload = json.loads(FIXTURES.read_text(encoding="utf-8"))["scenes"]
    assert payload["detector_version"] == file_version(DETECTOR)
    detector = OnnxPlateDetector(DETECTOR)
    pipeline = PlatePipeline(CRNNRecognizer("beam", MODEL, alpha=payload["alpha"]), detector)
    images = []
    for view in payload["views"]:
        image = as_u8(cv2.imread(str(ROOT / view["image"]), cv2.IMREAD_COLOR))
        assert list(image.shape[:2]) == [view["height"], view["width"]]
        boxes, scores = detector.raw_boxes(image)
        expected = np.asarray(view["detections"], dtype=np.float64)
        assert np.abs(np.asarray(boxes) - expected[:, :4]).max() < 1e-3
        assert np.abs(np.asarray(scores) - expected[:, 4]).max() < 1e-5
        images.append(image)
    result = pipeline.read(images)
    for view, expected_view in zip(result.views, payload["views"], strict=True):
        assert view.detection is not None
        assert view.read is not None
        assert list(view.detection.box) == expected_view["crop_box"]
        assert view.read.prediction == expected_view["prediction"]
        assert list(view.read.prediction_set or []) == (expected_view["prediction_set"] or [])
    fused = payload["fused"]
    assert result.fused.prediction == fused["prediction"]
    assert result.fused.confidence == pytest.approx(fused["confidence"], abs=1e-6)
    assert list(result.fused.prediction_set or []) == (fused["prediction_set"] or [])
    assert [p.symbol for p in result.fused.positions] == [p["symbol"] for p in fused["positions"]]


@pytest.mark.skipif(not (MODEL.exists() and DETECTOR.exists()), reason="no committed models")
def test_scene_fixture_writer_is_deterministic(tmp_path: Path) -> None:
    from plate_reader.parity import write_scene_fixtures

    first = write_scene_fixtures(MODEL, DETECTOR, tmp_path / "a", tmp_path, views=2)
    second = write_scene_fixtures(MODEL, DETECTOR, tmp_path / "b", tmp_path, views=2)
    for name in ("scene_00.png", "scene_01.png"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()

    def strip(payload: dict[str, object]) -> object:
        views = [{k: v for k, v in view.items() if k != "image"} for view in payload["views"]]  # type: ignore[attr-defined]
        return {**payload, "views": views}

    assert strip(first) == strip(second)
    assert first["alpha"] == 0.05
    assert len(first["views"]) == 2
