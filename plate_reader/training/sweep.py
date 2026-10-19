"""``plate sweep``: a domain-randomisation search over augmentation strengths.

The pseudo-real set stands in for the gap between synthetic and real photos, so the
question this answers is: which strengths of the generator's degradations make a CRNN
transfer best to images it was not generated for? Each trial scales five groups of
:class:`plate_reader.synthetic.augment.AugmentConfig` bounds (geometry, photometry, blur,
noise and compression, clutter) by a multiplier, fine-tunes the shipped CRNN for a short
budget on synthetic crops generated with them (a from-scratch CRNN needs several full epochs
before its accuracy says anything, which a sweep cannot afford per trial), and scores exact
match on a separate pseudo-real tuning split (its own seed, never the pseudo-real evaluation
set). Optuna's TPE sampler proposes the multipliers; the first trial is the shipped
configuration (every multiplier 1), and the shipped weights without any fine-tuning are
scored too, so both references are in the results.

Short fine-tunings rank configurations; they are not a retrained model.
Everything here is synthetic: synthetic results are not real-world accuracy, and once real
photos exist the objective should be their validation split instead of the pseudo-real one.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Final

import numpy as np

from ..docs_render import SYNTHETIC_LABEL
from ..synthetic.augment import DEFAULT, AugmentConfig
from ..synthetic.generate import GENERATOR_VERSION, make_pseudo_real
from ..synthetic.splits import SPLIT_SEEDS

Log = Callable[[str], object]

#: Each group's multiplier scales these AugmentConfig fields together.
GROUPS: Final[dict[str, tuple[str, ...]]] = {
    "geometry": ("perspective", "rotation_deg", "scale_jitter"),
    "photometry": ("brightness", "contrast", "gamma", "colour_cast"),
    "blur": ("motion_blur_px", "gaussian_sigma", "downscale"),
    "noise": ("noise_sigma", "jpeg_min_quality"),
    "clutter": (
        "shadow_prob",
        "shadow_depth",
        "dirt_prob",
        "dirt_blobs",
        "glare_prob",
        "occlusion_prob",
        "occlusion_frac",
    ),
}
BOUNDS: Final = (0.5, 2.0)
PROBABILITIES: Final = {"shadow_prob", "dirt_prob", "glare_prob", "occlusion_prob"}


def scaled_config(multipliers: Mapping[str, float], base: AugmentConfig = DEFAULT) -> AugmentConfig:
    """``base`` with every field of a group scaled by that group's multiplier.

    Probabilities stay in [0, 1] and depths and fractions below 1; JPEG quality scales the
    distance from 100 (a larger multiplier compresses harder); counts stay integers. A
    group whose base value is zero (glare in the default preset) gains the multiplier's
    excess as a probability of its own, so the search can switch it on.
    """
    values: dict[str, Any] = {}
    for group, names in GROUPS.items():
        m = float(multipliers.get(group, 1.0))
        for name in names:
            current = getattr(base, name)
            if name == "jpeg_min_quality":
                values[name] = int(np.clip(round(100 - (100 - current) * m), 5, 95))
            elif name == "dirt_blobs":
                values[name] = max(0, round(current * m))
            elif name in PROBABILITIES:
                scaled = current * m if current > 0 else max(0.0, (m - 1.0) * 0.25)
                values[name] = float(min(1.0, scaled))
            elif name in {"shadow_depth", "occlusion_frac", "downscale"}:
                values[name] = float(min(0.9, current * m))
            else:
                values[name] = float(current * m)
    return replace(base, **values)


@dataclass(frozen=True)
class SweepBudget:
    trials: int = 8
    epochs: int = 3
    epoch_size: int = 10000
    batch_size: int = 128
    lr: float = 5e-4
    tune_size: int = 1000
    val_size: int = 200
    workers: int = 6
    seed: int = 0
    device: str = "auto"


def correctness(logits: np.ndarray, truths: list[str]) -> np.ndarray:
    """1 where the greedy read equals the truth, per crop (the sweep's objective)."""
    from ..crnn.decode import greedy, log_softmax

    return np.array(
        [
            float(greedy(log_softmax(item))[0] == truth)
            for item, truth in zip(logits, truths, strict=True)
        ]
    )


def tuning_split(size: int) -> tuple[np.ndarray, list[str]]:
    from ..crnn.preprocess import batch

    samples = [make_pseudo_real(SPLIT_SEEDS["pseudo_real_tune"], i) for i in range(size)]
    return batch([s.image for s in samples]), [s.tokens for s in samples]


def run_sweep(
    budget: SweepBudget, work_dir: Path, init_weights: Path | None = None, log: Log = print
) -> dict[str, Any]:
    import optuna

    from ..eval.bootstrap import Bootstrap
    from .train_crnn import TrainConfig, load_weights, predict_logits, resolve_device, train

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    images, truths = tuning_split(budget.tune_size)
    device = resolve_device(budget.device)
    trials: list[dict[str, Any]] = []
    # One set of resamples for every trial, so differences are paired over the same crops.
    bootstrap = Bootstrap(len(truths), 1000, 0.95, budget.seed)
    outcomes: dict[int, np.ndarray] = {}
    shipped: dict[str, Any] | None = None
    if init_weights is not None:
        logits = predict_logits(load_weights(init_weights).to(device), images, device)
        shipped = bootstrap.mean(correctness(logits, truths)).as_dict()
        log(f"shipped weights before fine-tuning: {shipped['value']:.3f} pseudo-real exact match")

    def objective(trial: optuna.Trial) -> float:
        multipliers = {g: trial.suggest_float(g, *BOUNDS, log=True) for g in GROUPS}
        config = TrainConfig(
            epochs=budget.epochs,
            epoch_size=budget.epoch_size,
            batch_size=budget.batch_size,
            lr=budget.lr,
            curriculum_start=1.0,
            init_weights=init_weights,
            val_size=budget.val_size,
            workers=budget.workers,
            persistent_workers=False,
            seed=budget.seed,
            device=str(device),
            beam_every=10**6,
            fine_tune_epochs=0,
            checkpoint=work_dir / f"trial_{trial.number}.pt",
            augment=scaled_config(multipliers),
        )
        tick = time.perf_counter()
        result = train(config, log=lambda _: None)
        logits = predict_logits(result.model.to(device), images, device)
        correct = correctness(logits, truths)
        outcomes[trial.number] = correct
        estimate = bootstrap.mean(correct)
        score = estimate.value
        reference = outcomes.get(0)
        difference = (
            bootstrap.mean(correct - reference).as_dict() if reference is not None else None
        )
        seconds = round(time.perf_counter() - tick, 1)
        trials.append(
            {
                "number": trial.number,
                "multipliers": {g: round(v, 4) for g, v in multipliers.items()},
                "pseudo_real_exact_greedy": round(score, 6),
                "pseudo_real_ci": [round(estimate.ci_low, 6), round(estimate.ci_high, 6)],
                "difference_vs_trial_0": difference,
                "synthetic_val_exact_greedy": round(result.best_val, 6),
                "seconds": seconds,
            }
        )
        log(f"trial {trial.number}: {score:.3f} pseudo-real exact match in {seconds:.0f} s")
        return score

    sampler = optuna.samplers.TPESampler(seed=budget.seed)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.enqueue_trial(dict.fromkeys(GROUPS, 1.0))  # the shipped configuration first
    study.optimize(objective, n_trials=budget.trials)

    best = max(trials, key=lambda t: (t["pseudo_real_exact_greedy"], -t["number"]))
    baseline = trials[0]
    return {
        "schema": "detectionx5.sweep/1",
        "label": SYNTHETIC_LABEL,
        "generator_version": GENERATOR_VERSION,
        "objective": (
            "exact match (greedy) on the pseudo-real tuning split after a short fine-tuning"
            if init_weights is not None
            else "exact match (greedy) on the pseudo-real tuning split after a short training"
        ),
        "init_weights": init_weights.name if init_weights is not None else None,
        "shipped_before_fine_tuning": shipped,
        "bootstrap": bootstrap.describe("pseudo-real tuning crop") | {"paired": True},
        "splits": {
            "train": {"seed": SPLIT_SEEDS["train"]},
            "tuning": {"seed": SPLIT_SEEDS["pseudo_real_tune"], "n": budget.tune_size},
        },
        "budget": asdict(budget) | {"device": str(device)},
        "groups": {g: list(names) for g, names in GROUPS.items()},
        "bounds": list(BOUNDS),
        "sampler": "optuna TPE",
        "baseline": baseline,
        "best": best,
        "best_config": asdict(scaled_config(best["multipliers"])),
        "trials": trials,
        "adopted": False,
        "note": (
            "short fine-tunings rank augmentation strengths; the shipped CRNN keeps the "
            "default configuration until a full training with the best one is evaluated"
        ),
    }


__all__ = ["BOUNDS", "GROUPS", "SweepBudget", "run_sweep", "scaled_config", "tuning_split"]
