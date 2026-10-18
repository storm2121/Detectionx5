"""Metrics on recogniser outputs, each with a bootstrap interval.

Definitions (``truth`` and ``prediction`` are canonical token strings):

* exact match: the whole plate is right.
* per-field accuracy: digits, letter and region compared field by field after the
  grammar splits both strings; letter and region apply only to standard truths (a
  temporary plate has neither), so their n is smaller. A missing prediction counts wrong.
* character error rate (CER): Levenshtein distance between the printed characters
  (separators removed) divided by the truth's character count, summed over the corpus;
  a missing prediction costs the whole truth.
* read rate: share of images for which the recogniser returned any grammar-valid plate.
* expected calibration error (ECE): equal-width bins of the confidence of the top
  prediction, weighted gap between accuracy and mean confidence; a missing prediction
  has confidence 0 and is wrong.
* conformal coverage and set size: share of truths inside the prediction set, and the
  mean set size, when a recogniser returns sets.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

import numpy as np
import numpy.typing as npt

from ..grammar import GRAMMAR, LETTERS
from ..hypotheses import ViewRead
from ..strings import glyphs, levenshtein
from .bootstrap import Bootstrap

FloatArray = npt.NDArray[np.float64]
NONE_LABEL: Final = "none"
ECE_BINS: Final = 10


def _fields(tokens: str | None) -> dict[str, str]:
    if tokens is None:
        return {}
    split = GRAMMAR.segment(tokens)
    return split[1] if split else {}


def score_reads(truths: Sequence[str], reads: Sequence[ViewRead]) -> dict[str, FloatArray]:
    """Per-image score vectors; NaN where a metric does not apply."""
    if len(truths) != len(reads):
        raise ValueError("truths and reads must align")
    n = len(truths)
    out: dict[str, FloatArray] = {
        key: np.full(n, np.nan)
        for key in (
            "exact",
            "digits",
            "letter",
            "region",
            "format",
            "read",
            "edits",
            "glyphs",
            "confidence",
            "covered",
            "set_size",
            "latency_ms",
        )
    }
    for i, (truth, read) in enumerate(zip(truths, reads, strict=True)):
        pred = read.prediction
        t_fields, p_fields = _fields(truth), _fields(pred)
        out["exact"][i] = float(pred == truth)
        out["read"][i] = float(pred is not None)
        out["digits"][i] = float(p_fields.get("digits") == t_fields.get("digits"))
        if "letter" in t_fields:
            out["letter"][i] = float(p_fields.get("letter") == t_fields["letter"])
            out["region"][i] = float(p_fields.get("region") == t_fields["region"])
        out["format"][i] = float(
            pred is not None and GRAMMAR.format_of(pred) == GRAMMAR.format_of(truth)
        )
        truth_glyphs = glyphs(truth)
        out["glyphs"][i] = float(len(truth_glyphs))
        out["edits"][i] = float(
            levenshtein(glyphs(pred), truth_glyphs) if pred is not None else len(truth_glyphs)
        )
        out["confidence"][i] = (
            float(read.confidence) if read.confidence is not None and pred else 0.0
        )
        out["latency_ms"][i] = read.latency_ms
        if read.prediction_set is not None:
            out["covered"][i] = float(truth in read.prediction_set)
            out["set_size"][i] = float(len(read.prediction_set))
    return out


def _bin_of(confidence: FloatArray, bins: int) -> npt.NDArray[np.int64]:
    return np.minimum((confidence * bins).astype(np.int64), bins - 1)


def ece(confidence: FloatArray, correct: FloatArray, bins: int = ECE_BINS) -> float:
    if confidence.size == 0:
        return float("nan")
    which = _bin_of(confidence, bins)
    counts = np.bincount(which, minlength=bins).astype(np.float64)
    conf = np.bincount(which, weights=confidence, minlength=bins)
    acc = np.bincount(which, weights=correct, minlength=bins)
    occupied = counts > 0
    gaps = np.abs(acc[occupied] - conf[occupied])  # sums, so the gap is already weighted
    return float(gaps.sum() / confidence.size)


def reliability(
    confidence: FloatArray, correct: FloatArray, bins: int = ECE_BINS
) -> list[dict[str, Any]]:
    which = _bin_of(confidence, bins)
    rows = []
    for b in range(bins):
        mask = which == b
        count = int(mask.sum())
        rows.append(
            {
                "low": round(b / bins, 6),
                "high": round((b + 1) / bins, 6),
                "n": count,
                "accuracy": round(float(correct[mask].mean()), 6) if count else None,
                "confidence": round(float(confidence[mask].mean()), 6) if count else None,
            }
        )
    return rows


def letter_confusion(truths: Sequence[str], reads: Sequence[ViewRead]) -> dict[str, Any]:
    labels = [*LETTERS, NONE_LABEL]
    index = {label: i for i, label in enumerate(labels)}
    matrix = np.zeros((len(LETTERS), len(labels)), dtype=np.int64)
    for truth, read in zip(truths, reads, strict=True):
        letter = _fields(truth).get("letter")
        if letter is None:
            continue
        predicted = _fields(read.prediction).get("letter", NONE_LABEL)
        matrix[index[letter], index[predicted]] += 1
    return {"rows": list(LETTERS), "columns": labels, "matrix": matrix.tolist()}


def latency_summary(latency_ms: FloatArray) -> dict[str, float | None]:
    finite = latency_ms[np.isfinite(latency_ms)]
    if finite.size == 0:
        return {"p50": None, "p90": None, "p99": None, "mean": None}
    return {
        "p50": round(float(np.percentile(finite, 50)), 3),
        "p90": round(float(np.percentile(finite, 90)), 3),
        "p99": round(float(np.percentile(finite, 99)), 3),
        "mean": round(float(finite.mean()), 3),
    }


def summarise(
    truths: Sequence[str], reads: Sequence[ViewRead], bootstrap: Bootstrap
) -> dict[str, Any]:
    """Every metric for one recogniser on one population, with paired bootstrap CIs."""
    scores = score_reads(truths, reads)
    exact = scores["exact"]
    confidence = scores["confidence"]

    def ece_of(idx: npt.NDArray[np.int64]) -> float:
        return ece(confidence[idx], exact[idx])

    metrics = {
        "exact_match": bootstrap.mean(exact).as_dict(),
        "digits_accuracy": bootstrap.mean(scores["digits"]).as_dict(),
        "letter_accuracy": bootstrap.mean(scores["letter"]).as_dict(),
        "region_accuracy": bootstrap.mean(scores["region"]).as_dict(),
        "format_accuracy": bootstrap.mean(scores["format"]).as_dict(),
        "read_rate": bootstrap.mean(scores["read"]).as_dict(),
        "cer": bootstrap.ratio(scores["edits"], scores["glyphs"]).as_dict(),
        "mean_confidence": bootstrap.mean(confidence).as_dict(),
        "ece": bootstrap.statistic(ece_of).as_dict(),
    }
    if not np.all(np.isnan(scores["covered"])):
        metrics["coverage"] = bootstrap.mean(scores["covered"]).as_dict()
        metrics["set_size"] = bootstrap.mean(scores["set_size"]).as_dict()
    return {
        "n": len(truths),
        "metrics": metrics,
        "reliability": reliability(confidence, exact),
        "letter_confusion": letter_confusion(truths, reads),
        "latency_ms": latency_summary(scores["latency_ms"]),
    }


__all__ = [
    "ECE_BINS",
    "NONE_LABEL",
    "ece",
    "latency_summary",
    "letter_confusion",
    "reliability",
    "score_reads",
    "summarise",
]
