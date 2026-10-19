"""A paired comparison of two exported CRNNs on the same crops, with the served decoder.

``plate compare-crnn --old A.onnx --new B.onnx`` reads the synthetic test split and the
pseudo-real set with both models through the grammar-constrained beam (each with its own
calibrated temperature, as the service would run it) and reports each model's exact match
and the paired difference, new minus old, with a percentile bootstrap over the same
resampled crops. The adoption rule is fixed before the comparison runs (ADR 0010): the new
weights replace the old ones only when the interval of the difference on the synthetic
test split lies above zero. The pseudo-real set is reported, not used to decide.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final

import numpy as np

from ..docs_render import SYNTHETIC_LABEL
from ..settings import PROJECT_ROOT
from .bootstrap import Bootstrap
from .harness import read_all, set_header
from .metrics import score_reads
from .recognizers import CRNNRecognizer
from .sets import EvalSet, pseudo_real_set, synthetic_set

SCHEMA: Final = "detectionx5.compare_crnn/1"
DECIDING_SET: Final = "synthetic"
RULE: Final = (
    "adopt the new weights only if the paired difference in exact match (new minus old) on "
    "the synthetic test split has a bootstrap interval entirely above zero"
)
SETS: Final[dict[str, Callable[[int], EvalSet]]] = {
    "synthetic": synthetic_set,
    "pseudo_real": pseudo_real_set,
}


def _shown(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.name


def _model(path: Path, name: str) -> CRNNRecognizer:
    recognizer = CRNNRecognizer("beam", onnx_path=path)
    recognizer.name = name
    return recognizer


def _training(summary: Mapping[str, Any]) -> dict[str, Any]:
    config = summary.get("config", {})
    return {
        "epochs": config.get("epochs"),
        "epoch_size": config.get("epoch_size"),
        "seconds": summary.get("seconds"),
        "best_epoch": summary.get("best_epoch"),
        "best_val_exact_greedy": summary.get("best_val_exact_greedy"),
        "augment_source": summary.get("augment_source"),
    }


def compare_crnn(
    old: Path,
    new: Path,
    *,
    n: int = 2000,
    resamples: int = 1000,
    confidence: float = 0.95,
    seed: int = 0,
    quiet: bool = True,
    new_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Both models on ``n`` crops of each set, paired; the decision follows :data:`RULE`.

    ``new_summary`` is the candidate's ``train_crnn.json``: how it was trained is recorded
    with the comparison, whichever way it goes.
    """
    models = [_model(old, "old"), _model(new, "new")]
    bootstrap = Bootstrap(n, resamples, confidence, seed)
    sets: dict[str, Any] = {}
    for name, build in SETS.items():
        eval_set = build(n)
        truths = [item.truth for item in eval_set.items]
        reads = read_all(eval_set.items, models, eval_set.name, quiet)
        right_old = score_reads(truths, reads["old"])["exact"]
        right_new = score_reads(truths, reads["new"])["exact"]
        sets[name] = {
            "set": set_header(eval_set),
            "old": bootstrap.mean(right_old).as_dict(),
            "new": bootstrap.mean(right_new).as_dict(),
            "difference": bootstrap.mean(right_new - right_old).as_dict(),
            "only_old_right": int(np.sum((right_old == 1) & (right_new == 0))),
            "only_new_right": int(np.sum((right_new == 1) & (right_old == 0))),
        }
    low = sets[DECIDING_SET]["difference"]["ci_low"]
    adopt = low is not None and float(low) > 0.0
    return {
        "schema": SCHEMA,
        "label": SYNTHETIC_LABEL,
        "metric": "exact match of the grammar-constrained beam (the served decoder)",
        "old": {"file": _shown(old), "version": models[0].version},
        "new": {"file": _shown(new), "version": models[1].version}
        | ({"training": _training(new_summary)} if new_summary is not None else {}),
        "bootstrap": bootstrap.describe("crop") | {"paired": True},
        "sets": sets,
        "deciding_set": DECIDING_SET,
        "rule": RULE,
        "adopt": adopt,
    }


__all__ = ["DECIDING_SET", "RULE", "SCHEMA", "compare_crnn"]
