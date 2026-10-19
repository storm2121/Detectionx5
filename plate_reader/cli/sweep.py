"""``plate sweep``: a domain-randomisation search over augmentation strengths (Optuna)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

HELP = "Search augmentation strengths against the pseudo-real set (Optuna)."


def command(
    trials: Annotated[
        int, typer.Option(min=1, help="trials, the first being the shipped configuration")
    ] = 8,
    epochs: Annotated[int, typer.Option(min=1, help="epochs per trial")] = 3,
    epoch_size: Annotated[int, typer.Option(min=32, help="synthetic crops per epoch")] = 10000,
    tune_size: Annotated[int, typer.Option(min=10, help="pseudo-real tuning crops")] = 1000,
    device: Annotated[str, typer.Option(help="auto, cpu or cuda")] = "auto",
    seed: Annotated[int, typer.Option(help="sampler and training seed")] = 0,
    weights: Annotated[
        Path | None, typer.Option(help="weights each trial fine-tunes (default models/crnn.pt)")
    ] = None,
    scratch: Annotated[bool, typer.Option(help="train each trial from scratch instead")] = False,
    out: Annotated[Path | None, typer.Option(help="default results/sweep.json")] = None,
) -> None:
    """Short CRNN fine-tunings with scaled augmentation groups, scored on pseudo-real crops."""
    from ..settings import PROJECT_ROOT
    from ..training.sweep import SweepBudget, run_sweep

    budget = SweepBudget(
        trials=trials,
        epochs=epochs,
        epoch_size=epoch_size,
        tune_size=tune_size,
        seed=seed,
        device=device,
    )
    work = PROJECT_ROOT / ".cache" / "sweep"
    work.mkdir(parents=True, exist_ok=True)
    init = None if scratch else (weights or PROJECT_ROOT / "models" / "crnn.pt")
    if init is not None and not init.exists():
        raise typer.BadParameter(f"{init} does not exist; train the CRNN or pass --scratch")
    payload = run_sweep(budget, work, init, log=typer.echo)
    target = out or PROJECT_ROOT / "results" / "sweep.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    best = payload["best"]
    typer.echo(
        f"wrote {target}: best trial {best['number']} at {best['pseudo_real_exact_greedy']:.3f} "
        f"(shipped configuration {payload['baseline']['pseudo_real_exact_greedy']:.3f}); synthetic"
    )


__all__ = ["HELP", "command"]
