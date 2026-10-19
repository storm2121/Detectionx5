"""``plate compare-crnn``: two exported CRNNs on the same crops, paired."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

HELP = "Compare two exported CRNNs on the same crops (paired bootstrap)."


def command(
    old: Annotated[Path, typer.Option(help="the CRNN in service (an exported crnn.onnx)")],
    new: Annotated[Path, typer.Option(help="the candidate (an exported crnn.onnx)")],
    n: Annotated[int, typer.Option(min=20, help="crops per set")] = 2000,
    resamples: Annotated[int, typer.Option(min=100)] = 1000,
    new_summary: Annotated[
        Path | None, typer.Option(help="the candidate's train_crnn.json, recorded with it")
    ] = None,
    out: Annotated[
        Path | None, typer.Option(help="results file (default results/crnn_comparison.json)")
    ] = None,
) -> None:
    """Read the synthetic test split and the pseudo-real set with both models and compare."""
    from ..eval.compare import compare_crnn
    from ..settings import get_settings

    for path in (old, new):
        if not path.exists():
            raise typer.BadParameter(f"{path} does not exist")
    summary = (
        json.loads(new_summary.read_text(encoding="utf-8")) if new_summary is not None else None
    )
    payload = compare_crnn(old, new, n=n, resamples=resamples, new_summary=summary)
    target = out or get_settings().results_dir / "crnn_comparison.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, entry in payload["sets"].items():
        d = entry["difference"]
        typer.echo(
            f"{name}: old {entry['old']['value']:.4f}, new {entry['new']['value']:.4f}, "
            f"difference {d['value']:+.4f} [{d['ci_low']:+.4f}, {d['ci_high']:+.4f}]"
        )
    verdict = "adopt the new weights" if payload["adopt"] else "keep the old weights"
    typer.echo(f"{verdict} ({payload['rule']}); synthetic results are not real-world accuracy")


__all__ = ["HELP", "command"]
