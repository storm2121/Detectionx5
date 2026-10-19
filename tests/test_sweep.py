"""The domain-randomisation sweep: scaled augmentation presets and a tiny end-to-end run."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest

from plate_reader.synthetic.augment import DEFAULT
from plate_reader.training.sweep import GROUPS, SweepBudget, run_sweep, scaled_config, tuning_split


def test_unit_multipliers_keep_the_shipped_configuration() -> None:
    assert scaled_config(dict.fromkeys(GROUPS, 1.0)) == DEFAULT


@pytest.mark.parametrize("m", [0.5, 2.0, 4.0])
def test_scaled_configurations_stay_valid(m: float) -> None:
    config = scaled_config(dict.fromkeys(GROUPS, m))
    for name in ("shadow_prob", "dirt_prob", "glare_prob", "occlusion_prob"):
        assert 0.0 <= getattr(config, name) <= 1.0
    assert 5 <= config.jpeg_min_quality <= 95
    assert config.downscale <= 0.9
    assert isinstance(config.dirt_blobs, int)
    if m > 1:
        assert config.perspective > DEFAULT.perspective
        assert config.jpeg_min_quality < DEFAULT.jpeg_min_quality
        assert config.glare_prob > 0.0  # off in the default preset, switched on by the search
    else:
        assert config.noise_sigma < DEFAULT.noise_sigma


def test_tuning_split_is_its_own_pseudo_real_stream() -> None:
    images, truths = tuning_split(4)
    again, truths_again = tuning_split(4)
    assert images.shape == (4, 1, 32, 160)
    assert (images == again).all()
    assert truths == truths_again


def test_a_tiny_sweep_runs_and_ranks_the_shipped_configuration_first(tmp_path: Path) -> None:
    budget = SweepBudget(
        trials=2,
        epochs=1,
        epoch_size=64,
        batch_size=32,
        tune_size=8,
        val_size=8,
        workers=0,
        device="cpu",
    )
    weights = Path(__file__).resolve().parents[1] / "models" / "crnn.pt"
    payload = run_sweep(budget, tmp_path, weights if weights.exists() else None, log=lambda _: None)
    assert payload["label"] == "synthetic results are not real-world accuracy"
    assert len(payload["trials"]) == 2
    assert payload["baseline"]["number"] == 0
    assert payload["baseline"]["multipliers"] == dict.fromkeys(GROUPS, 1.0)
    best = max(t["pseudo_real_exact_greedy"] for t in payload["trials"])
    assert payload["best"]["pseudo_real_exact_greedy"] == best
    assert payload["best_config"] == asdict(scaled_config(payload["best"]["multipliers"]))
    assert payload["adopted"] is False
    if weights.exists():
        assert payload["init_weights"] == "crnn.pt"
        assert 0.0 <= payload["shipped_before_fine_tuning"]["value"] <= 1.0
    first, second = payload["trials"]
    assert first["difference_vs_trial_0"]["value"] == 0.0
    low, high = second["pseudo_real_ci"]
    assert low <= second["pseudo_real_exact_greedy"] <= high
    assert payload["bootstrap"]["paired"] is True
