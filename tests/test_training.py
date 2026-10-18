"""Training data, a tiny CPU training run, export, runtime and calibration (smoke)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import torch

from plate_reader import grammar
from plate_reader.crnn.charset import CHARSET_ID, decode
from plate_reader.crnn.model import CRNN, CRNNConfig, count_parameters
from plate_reader.crnn.runtime import CRNNMetadata, CRNNRuntime, metadata_path_for
from plate_reader.synthetic import make_crop, write_crops
from plate_reader.training.calibrate_crnn import calibrate
from plate_reader.training.data import (
    Curriculum,
    EpochSampler,
    LabelledCrops,
    SyntheticCrops,
    collate,
)
from plate_reader.training.export_onnx import export_onnx, write_metadata
from plate_reader.training.train_crnn import (
    TrainConfig,
    exact_match,
    load_weights,
    predict_logits,
    resolve_device,
    save_weights,
    train,
    training_summary,
)


def test_curriculum_rises_to_full_strength() -> None:
    curriculum = Curriculum(epochs=10, start=0.3, ramp_fraction=0.5)
    values = [curriculum.upper(e) for e in range(10)]
    assert values[0] == pytest.approx(0.3)
    assert values == sorted(values)
    assert values[-1] == 1.0


def test_epoch_sampler_is_seeded_and_covers_the_epoch_slice() -> None:
    sampler = EpochSampler(8, seed=1)
    sampler.set_epoch(2)
    first = list(sampler)
    assert sorted(first) == list(range(16, 24))
    sampler.set_epoch(2)
    assert list(sampler) == first
    assert len(sampler) == 8


def test_synthetic_stream_items_and_collate() -> None:
    dataset = SyntheticCrops(seed=3, epoch_size=4, curriculum=Curriculum(epochs=2))
    assert len(dataset) == 8
    image, target = dataset[5]
    assert image.shape == (1, 32, 160)
    assert grammar.accepts(decode(target))
    again, _ = dataset[5]
    assert torch.equal(image, again)
    images, targets, lengths = collate([dataset[0], dataset[1]])
    assert images.shape == (2, 1, 32, 160)
    assert int(lengths.sum()) == targets.numel()


def test_model_shapes_and_size() -> None:
    model = CRNN().eval()
    out = model(torch.zeros(3, 1, 32, 160))
    assert out.shape == (3, 40, model.config.num_classes)
    # Comfortably under the 15 MB per-model limit at fp32.
    assert count_parameters(model) * 4 < 15 * 1024 * 1024
    config = CRNNConfig.from_dict(model.config.as_dict())
    assert config == model.config


@pytest.mark.slow
def test_tiny_training_export_runtime_and_calibration(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    write_crops(data_dir / "ocr" / "train", 8, seed=9)
    config = TrainConfig(
        epochs=2,
        epoch_size=32,
        batch_size=8,
        workers=0,
        val_size=8,
        device="cpu",
        beam_every=1,
        fine_tune_epochs=1,
        data_dir=data_dir,
        checkpoint=tmp_path / "checkpoints" / "best.pt",
    )
    messages: list[str] = []
    result = train(config, log=messages.append)
    assert len(result.history) == 3
    assert result.fine_tuned
    assert "val_exact_beam" in result.history[0]
    assert config.checkpoint.exists()
    summary = training_summary(config, result)
    assert summary["fine_tuned_on_real_data"] is True
    json.dumps(summary)

    weights = save_weights(result.model, tmp_path / "crnn.pt")
    reloaded = load_weights(weights)
    probe = torch.zeros(1, 1, 32, 160)
    assert torch.allclose(reloaded(probe), result.model.eval()(probe), atol=1e-6)

    onnx_path = export_onnx(reloaded, tmp_path / "crnn.onnx")
    meta = write_metadata(onnx_path, CRNNMetadata(version=""))
    assert meta.version
    assert meta.charset_id == CHARSET_ID
    runtime = CRNNRuntime(onnx_path)
    crop = make_crop(1, 0).image
    for decoder in ("beam", "greedy", "unconstrained"):
        read = runtime.read(crop, decoder)  # type: ignore[arg-type]
        assert read.latency_ms >= 0
        assert all(grammar.accepts(h.tokens) for h in read.hypotheses)

    payload = calibrate(onnx_path, 12, 12, 12, resamples=100, log=messages.append)
    assert payload["label"] == "synthetic results are not real-world accuracy"
    assert set(payload["conformal"]["coverage"]) == {"0.1", "0.05"}
    calibrated = CRNNMetadata.load(metadata_path_for(onnx_path))
    assert calibrated.calibrated
    assert set(calibrated.conformal) == {"0.1", "0.05"}

    from plate_reader.eval.recognizers import CRNNRecognizer
    from plate_reader.training.calibrate_fused import calibrate_fused

    fused = calibrate_fused(onnx_path, 6, n_test=4, resamples=50, log=messages.append)
    assert set(fused["thresholds"]) == {"1", "3", "5"}
    assert fused["label"] == "synthetic results are not real-world accuracy"
    recognizer = CRNNRecognizer("beam", onnx_path, alpha=0.1)
    table = recognizer.runtime.metadata.conformal_fused
    assert recognizer.conformal_threshold_for(4) == table["3"]["0.1"]
    assert recognizer.conformal_threshold_for(9) == table["5"]["0.1"]
    assert recognizer.conformal_threshold_for(1) == table["1"]["0.1"]
    assert CRNNRecognizer("greedy", onnx_path).conformal_threshold_for(3) is None

    logits = predict_logits(
        reloaded, np.zeros((2, 1, 32, 160), dtype=np.float32), torch.device("cpu")
    )
    assert logits.shape == (2, 40, reloaded.config.num_classes)
    assert 0.0 <= exact_match(logits, ["1-WW", "2-WW"], beam=True) <= 1.0
    assert resolve_device("cpu").type == "cpu"


def test_labelled_crops_and_runtime_refuses_a_foreign_charset(tmp_path: Path) -> None:
    write_crops(tmp_path / "crops", 3, seed=2)
    crops = LabelledCrops(tmp_path / "crops" / "labels.csv")
    image, target = crops[0]
    assert image.shape == (1, 32, 160)
    assert grammar.accepts(decode(target))
    onnx_path = export_onnx(CRNN().eval(), tmp_path / "m.onnx")
    write_metadata(onnx_path, CRNNMetadata(version="", charset_id="different"))
    with pytest.raises(ValueError):
        CRNNRuntime(onnx_path)
    bad = tmp_path / "bad.csv"
    bad.write_text("crop_path,plate_text,format\nx.png,nope,standard\n", encoding="utf-8")
    with pytest.raises(ValueError):
        LabelledCrops(bad)
