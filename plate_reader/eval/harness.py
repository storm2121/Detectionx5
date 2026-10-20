"""The evaluation harness: run recognisers over a set, score them, write results JSON.

Results are written to ``results/eval_<set>.json`` without timestamps or machine paths, so
re-running an unchanged evaluation reproduces the file and the README (which renders from
it) does not drift. Every payload carries its set kind, n, the bootstrap description and
each recogniser's version, and synthetic payloads carry the synthetic label.

A photo read end to end where the detector found nothing has no crop; it is scored as a read
that returned nothing (no plate, no confidence, an empty set when the recogniser makes
sets), never dropped, so a missed plate costs what it costs the service.
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import numpy as np

from .. import __version__
from ..docs_render import SYNTHETIC_LABEL
from ..fusion import Fuser, legacy_vote, probabilistic_fusion, quality_weight
from ..hypotheses import ViewRead
from ..synthetic.augment import sharpness
from .bootstrap import Bootstrap
from .cache import ReadCache
from .metrics import score_reads, summarise
from .recognizers import Recognizer
from .sets import EvalSet

SCHEMA: Final = "detectionx5.eval/1"
DEFAULT_KS: Final = (1, 3, 5)

#: name -> (fuser, view weighting). "uniform" weights every view 1; "quality" weights a view
#: by its image sharpness (crops have no detector confidence to multiply in).
DEFAULT_FUSERS: Final[dict[str, tuple[Fuser, str]]] = {
    "legacy_vote": (legacy_vote, "uniform"),
    "probabilistic": (probabilistic_fusion, "uniform"),
    "probabilistic_weighted": (probabilistic_fusion, "quality"),
}
Progress = Callable[[str], object]


def _progress_printer(total: int, label: str) -> Callable[[int], None]:
    start = time.perf_counter()

    def report(done: int) -> None:
        if done == total or done % 25 == 0:
            elapsed = time.perf_counter() - start
            eta = elapsed / done * (total - done) if done else 0.0
            print(f"  {label}: {done}/{total} ({elapsed:.0f}s, eta {eta:.0f}s)", file=sys.stderr)

    return report


def nothing_read(recognizer: Recognizer) -> ViewRead:
    """The read of a photo without a crop: no plate, and an empty set if sets are made."""
    makes_sets = getattr(recognizer, "conformal_threshold", None) is not None
    return ViewRead(prediction_set=() if makes_sets else None, latency_ms=float("nan"))


def read_all(
    items: Sequence[Any],
    recognizers: Sequence[Recognizer],
    label: str,
    quiet: bool = False,
    cache: ReadCache | None = None,
) -> dict[str, list[ViewRead]]:
    reads: dict[str, list[ViewRead]] = {r.name: [] for r in recognizers}
    warmed: set[str] = set()
    report = _progress_printer(len(items), label)
    for done, item in enumerate(items, start=1):
        if item.image.size == 0:
            for recognizer in recognizers:
                reads[recognizer.name].append(nothing_read(recognizer))
            if not quiet:
                report(done)
            continue
        for recognizer in recognizers:
            cacheable = cache is not None and bool(getattr(recognizer, "cacheable", False))
            key = (
                ReadCache.key(recognizer.name, recognizer.version, item.image) if cacheable else ""
            )
            read = cache.get(key) if cache is not None and cacheable else None
            if read is None:
                if recognizer.name not in warmed:
                    # Model loading must not be timed as the first image's latency.
                    warmup = getattr(recognizer, "warmup", None)
                    if callable(warmup):
                        warmup()
                    warmed.add(recognizer.name)
                read = recognizer.read(item.image)
                if cache is not None and cacheable:
                    cache.put(key, read)
            reads[recognizer.name].append(read)
        if not quiet:
            report(done)
    return reads


def evaluate_recognizers(
    eval_set: EvalSet,
    recognizers: Sequence[Recognizer],
    bootstrap: Bootstrap,
    reads: Mapping[str, list[ViewRead]] | None = None,
    quiet: bool = False,
    cache: ReadCache | None = None,
) -> dict[str, Any]:
    truths = [item.truth for item in eval_set.items]
    reads = reads or read_all(eval_set.items, recognizers, eval_set.name, quiet, cache)
    out: dict[str, Any] = {}
    exact: dict[str, np.ndarray] = {}
    for recognizer in recognizers:
        summary = summarise(truths, reads[recognizer.name], bootstrap)
        summary["model_version"] = recognizer.version
        summary["calibrated"] = any(r.calibrated for r in reads[recognizer.name])
        out[recognizer.name] = summary
        exact[recognizer.name] = score_reads(truths, reads[recognizer.name])["exact"]
    names = [r.name for r in recognizers]
    comparisons = {}
    for other in names[1:]:
        diff = bootstrap.mean(exact[other] - exact[names[0]])
        comparisons[f"{other} - {names[0]}"] = {"exact_match_difference": diff.as_dict()}
    return {"recognizers": out, "comparisons": comparisons}


def evaluate_fusion(
    view_set: EvalSet,
    recognizers: Sequence[Recognizer],
    resamples: int,
    confidence: float,
    seed: int,
    ks: Sequence[int] = DEFAULT_KS,
    fusers: Mapping[str, tuple[Fuser, str]] = DEFAULT_FUSERS,
    reads: Mapping[str, list[ViewRead]] | None = None,
    quiet: bool = False,
    cache: ReadCache | None = None,
) -> dict[str, Any]:
    """Fuse the first ``k`` views of every set; the bootstrap unit is the set."""
    groups: dict[int, list[int]] = defaultdict(list)
    for position, item in enumerate(view_set.items):
        groups[item.group].append(position)
    order = sorted(groups)
    for g in order:
        groups[g].sort(key=lambda p: view_set.items[p].view)
    truths = [view_set.items[groups[g][0]].truth for g in order]
    reads = reads or read_all(view_set.items, recognizers, "views", quiet, cache)
    quality = [quality_weight(sharpness(item.image)) for item in view_set.items]
    bootstrap = Bootstrap(len(order), resamples, confidence, seed)
    out: dict[str, Any] = {}
    for recognizer in recognizers:
        per_view = reads[recognizer.name]
        single = getattr(recognizer, "conformal_threshold", None)
        threshold_for = getattr(recognizer, "conformal_threshold_for", None)
        methods: dict[str, Any] = {}
        for method, (fuse, weighting) in fusers.items():
            by_k: dict[str, Any] = {}
            for k in ks:
                fused = []
                for g in order:
                    members = groups[g][:k]
                    # As in the service: the threshold for the number of views that proposed
                    # a plate (a view proposing nothing contributes nothing to the fusion).
                    proposing = sum(1 for p in members if per_view[p].hypotheses)
                    threshold = threshold_for(proposing) if callable(threshold_for) else single
                    fused.append(
                        fuse(
                            [per_view[p] for p in members],
                            [quality[p] for p in members] if weighting == "quality" else None,
                            threshold,
                        )
                    )
                as_reads = [
                    ViewRead(
                        prediction=f.prediction,
                        confidence=f.confidence,
                        prediction_set=f.prediction_set,
                    )
                    for f in fused
                ]
                summary = summarise(truths, as_reads, bootstrap)
                by_k[f"k={k}"] = {
                    "metrics": summary["metrics"],
                    "reliability": summary["reliability"],
                }
            methods[method] = by_k
        out[recognizer.name] = {"model_version": recognizer.version, "methods": methods}
    return {
        "n_sets": len(order),
        "k": list(ks),
        "bootstrap": bootstrap.describe("multi-view set"),
        "recognizers": out,
    }


def set_header(eval_set: EvalSet) -> dict[str, Any]:
    return {"name": eval_set.name, "kind": eval_set.kind, "n": len(eval_set.items), **eval_set.info}


def detection_summary(eval_set: EvalSet, bootstrap: Bootstrap) -> dict[str, Any] | None:
    """For a set read end to end: how often the read crop lies on a labelled plate."""
    flags = [item.meta.get("on_plate") for item in eval_set.items]
    if not flags or any(flag is None for flag in flags):
        return None
    on_plate = np.asarray(flags, dtype=np.float64)
    missed = sum(1 for item in eval_set.items if item.image.size == 0)
    return {
        "photos": len(flags),
        "no_detection": missed,
        "off_plate": int(len(flags) - missed - on_plate.sum()),
        "on_plate": bootstrap.mean(on_plate).as_dict(),
        "rule": "the most confident detection overlaps the labelled plate's padded box by at "
        "least one half (intersection over union)",
    }


def build_payload(
    eval_set: EvalSet,
    recognizers: Sequence[Recognizer],
    *,
    resamples: int,
    confidence: float,
    seed: int,
    views: EvalSet | None = None,
    ks: Sequence[int] = DEFAULT_KS,
    device: str = "cpu",
    quiet: bool = False,
    cache: ReadCache | None = None,
) -> dict[str, Any]:
    groups = [item.group for item in eval_set.items] if eval_set.grouped else None
    bootstrap = Bootstrap(len(eval_set.items), resamples, confidence, seed, groups=groups)
    payload: dict[str, Any] = {"schema": SCHEMA}
    if eval_set.kind != "data":
        payload["label"] = SYNTHETIC_LABEL
    payload["set"] = set_header(eval_set)
    payload["bootstrap"] = bootstrap.describe("image")
    detection = detection_summary(eval_set, bootstrap)
    if detection is not None:
        payload["detection"] = detection
    # When the evaluated set is the multi-view set itself, read it once for both tables.
    shared = (
        read_all(eval_set.items, recognizers, eval_set.name, quiet, cache)
        if views is eval_set
        else None
    )
    payload.update(
        evaluate_recognizers(
            eval_set, recognizers, bootstrap, reads=shared, quiet=quiet, cache=cache
        )
    )
    if views is not None:
        payload["fusion"] = {
            "set": set_header(views),
            **evaluate_fusion(
                views,
                recognizers,
                resamples,
                confidence,
                seed,
                ks,
                reads=shared,
                quiet=quiet,
                cache=cache,
            ),
        }
    payload["environment"] = {"package_version": __version__, "device": device}
    return payload


def write_payload(payload: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    # LF on every platform, so re-running an unchanged evaluation reproduces the file.
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


__all__ = [
    "DEFAULT_FUSERS",
    "DEFAULT_KS",
    "SCHEMA",
    "build_payload",
    "detection_summary",
    "evaluate_fusion",
    "evaluate_recognizers",
    "nothing_read",
    "read_all",
    "set_header",
    "write_payload",
]
