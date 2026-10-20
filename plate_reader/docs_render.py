"""Render governed documentation blocks from measured results, and check for drift.

No number is typed by hand in a document: every metric in a governed file sits inside a
block delimited by ``<!-- BEGIN RENDER name -->`` and ``<!-- END RENDER name -->`` whose
content is generated from ``docs/training_results.csv`` and ``results/*.json``.

``check`` fails when

* a block's content differs from what the sources render today (drift: somebody edited a
  number by hand, or the results changed without re-rendering);
* a metric-like number (a decimal such as ``0.956`` or a percentage) appears in prose
  outside any block, which is how a hand-typed number sneaks back in;
* a block name is unknown or a block is not closed;
* the honesty statements are missing: synthetic metrics must carry the sentence
  :data:`SYNTHETIC_LABEL`, and :data:`NO_REAL_BENCHMARK` must stay while no real
  labelled evaluation exists.
"""

from __future__ import annotations

import csv
import difflib
import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Final

from .settings import PROJECT_ROOT

SYNTHETIC_LABEL: Final = "synthetic results are not real-world accuracy"
NO_REAL_BENCHMARK: Final = "OCR accuracy is not benchmarked on real data"

GOVERNED_FILES: Final[tuple[str, ...]] = (
    "README.md",
    "docs/model_card.md",
    "docs/data_card.md",
    "docs/methods/fusion.md",
    "docs/CV_NOTES.md",
)

_BLOCK_RE: Final = re.compile(
    r"<!-- BEGIN RENDER (?P<name>[a-z0-9-]+) -->\n(?P<body>.*?)<!-- END RENDER (?P=name) -->",
    re.DOTALL,
)
_OPEN_RE: Final = re.compile(r"<!-- BEGIN RENDER (?P<name>[a-z0-9-]+) -->")
_FENCE_RE: Final = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.DOTALL | re.MULTILINE)
_INLINE_CODE_RE: Final = re.compile(r"`[^`\n]*`")
_COMMENT_RE: Final = re.compile(r"<!--.*?-->", re.DOTALL)
# A decimal in [0, 1] with at least two places, a decimal percentage, or an integer
# percentage: the shapes metrics take. Configuration values live in code spans.
_METRIC_RE: Final = re.compile(
    r"(?<![\w.])(?:0\.\d{2,}|1\.0{2,})(?![\w.])|(?<![\w.])\d{1,3}(?:\.\d+)?\s?%"
)


@dataclass(frozen=True)
class Problem:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass
class RenderContext:
    """Lazy access to every source a block may render from."""

    root: Path = PROJECT_ROOT
    _json_cache: dict[str, Any] = field(default_factory=dict)

    @property
    def results_dir(self) -> Path:
        return self.root / "results"

    def result(self, name: str) -> Any | None:
        """Parsed ``results/<name>.json`` or ``None`` when it does not exist yet."""
        if name not in self._json_cache:
            path = self.results_dir / f"{name}.json"
            self._json_cache[name] = (
                json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            )
        return self._json_cache[name]

    @cached_property
    def training_rows(self) -> list[dict[str, float]]:
        path = self.root / "docs" / "training_results.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, skipinitialspace=True)
            return [
                {key.strip(): float(value) for key, value in row.items() if key} for row in reader
            ]

    def file_version(self, relative: str) -> str:
        """Short content hash used as the model version of a committed artefact."""
        path = self.root / relative
        if not path.exists():
            return "missing"
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def fmt(value: float, places: int = 3) -> str:
    return f"{value:.{places}f}"


def fmt_ci(metric: Mapping[str, Any], places: int = 3) -> str:
    """``value [low, high]`` for a metric dictionary written by the harness."""
    value = metric.get("value")
    if value is None:
        return "n/a"
    low, high = metric.get("ci_low"), metric.get("ci_high")
    if low is None or high is None:
        return fmt(float(value), places)
    return f"{fmt(float(value), places)} [{fmt(float(low), places)}, {fmt(float(high), places)}]"


# --- blocks ---------------------------------------------------------------------
BlockRenderer = Callable[[RenderContext], str]
BLOCKS: dict[str, BlockRenderer] = {}


def block(name: str) -> Callable[[BlockRenderer], BlockRenderer]:
    def register(func: BlockRenderer) -> BlockRenderer:
        BLOCKS[name] = func
        return func

    return register


def ultralytics_fitness(row: Mapping[str, float]) -> float:
    """Ultralytics picks ``best.pt`` by this weighted mAP; reproduce its choice exactly."""
    return 0.1 * row["metrics/mAP50(B)"] + 0.9 * row["metrics/mAP50-95(B)"]


def best_detector_epoch(ctx: RenderContext) -> dict[str, float]:
    rows = ctx.training_rows
    # The first maximum wins, matching the trainer's strict ``>`` comparison.
    best = rows[0]
    for row in rows[1:]:
        if ultralytics_fitness(row) > ultralytics_fitness(best):
            best = row
    return best


@block("detector-metrics")
def _detector_metrics(ctx: RenderContext) -> str:
    row = best_detector_epoch(ctx)
    epochs = len(ctx.training_rows)
    version = ctx.file_version("models/best.pt")
    lines = [
        f"`models/best.pt` (version `{version}`): YOLOv10n fine-tuned for {epochs} epochs on a "
        "single `LP` class, trained on a plate dataset plus photos from the firm's experts. "
        f"The shipped checkpoint is epoch {int(row['epoch'])}, the epoch Ultralytics selected "
        "by its fitness score (0.1 x mAP@50 + 0.9 x mAP@50-95). Values are from that epoch's "
        "row of the training log.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Precision | {fmt(row['metrics/precision(B)'])} |",
        f"| Recall | {fmt(row['metrics/recall(B)'])} |",
        f"| mAP@50 | {fmt(row['metrics/mAP50(B)'])} |",
        f"| mAP@50-95 | {fmt(row['metrics/mAP50-95(B)'])} |",
        "",
        "Set: the detector's own validation split (data). The training log does not record "
        "the split size, and a single validation pass gives no confidence interval, so "
        "neither n nor a CI is reported for these four numbers.",
    ]
    return "\n".join(lines)


def _precision_gap(metrics: Mapping[str, Any]) -> list[str]:
    """The detector's precision gap on synthetic scenes, as a paragraph (or nothing)."""
    gap = float(metrics.get("recall", 0.0)) - float(metrics.get("precision", 0.0))
    if gap <= 0:
        return []
    return [
        f"Precision is below recall by {fmt(gap)}: on these scenes the detector proposes boxes "
        "that are not plates more often than it misses a plate. The gap is noted and not acted "
        "on: the detector is not fine-tuned on synthetic scenes, and only a labelled set of real "
        "photos can say whether it matters.",
        "",
    ]


@block("detector-synthetic")
def _detector_synthetic(ctx: RenderContext) -> str:
    payload = ctx.result("eval_detector_synthetic")
    if payload is None:
        return (
            "Not measured yet: `uv run plate synth scenes --out synthetic/scenes-eval` then "
            "`uv run plate eval-detector --data synthetic/scenes-eval/detector.yaml`. "
            f"{SYNTHETIC_LABEL.capitalize()}."
        )
    metrics = payload.get("metrics", {})
    info = payload.get("set", {})
    counts = payload.get("counts", {})
    images, plates = counts.get("images"), counts.get("plates")
    with_plates = counts.get("images_with_plates")
    scope = (
        f"{images} scenes holding {plates} plates ({images - with_plates} with no plate)"
        if None not in (images, plates, with_plates)
        else "the whole split"
    )
    data = str(payload.get("data", "synthetic/scenes-eval/detector.yaml"))
    folder = data.rsplit("/", 1)[0] if "/" in data else "."
    lines = [
        f"**{SYNTHETIC_LABEL.capitalize()}.** `models/{payload.get('weights', '?')}` on the "
        f"`{payload.get('split', '?')}` split of a synthetic street-scene set: {scope}, "
        f"generator seed {info.get('seed', '?')}, version {info.get('generator_version', '?')}, "
        f"image size {payload.get('imgsz', '?')}. One Ultralytics validation pass, so no "
        "interval; procedural scenes say nothing about real photos.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Precision | {fmt(float(metrics.get('precision', 0.0)))} |",
        f"| Recall | {fmt(float(metrics.get('recall', 0.0)))} |",
        f"| mAP@50 | {fmt(float(metrics.get('map50', 0.0)))} |",
        f"| mAP@50-95 | {fmt(float(metrics.get('map50_95', 0.0)))} |",
        "",
        *_precision_gap(metrics),
        f"Reproduce: `uv run plate synth scenes --n {info.get('n', '?')} --seed "
        f"{info.get('seed', '?')} --val-fraction {info.get('val_fraction', '?')} --out {folder}` "
        f"then `uv run plate eval-detector --data {data}`.",
    ]
    return "\n".join(lines)


RECOGNIZER_NAMES: Final = {
    "easyocr": "EasyOCR path",
    "crnn-greedy": "CRNN, greedy",
    "crnn-beam": "CRNN, constrained beam",
    "crnn-beam-unconstrained": "CRNN, unconstrained beam",
}
RECOGNIZER_PROSE: Final = {
    "easyocr": "the EasyOCR path",
    "crnn-greedy": "the CRNN with greedy decoding",
    "crnn-beam": "the CRNN with the constrained beam",
    "crnn-beam-unconstrained": "the CRNN with the unconstrained beam",
}
_SMALL_NUMBERS: Final = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
]


def pct(value: float) -> str:
    """A rate as a whole per cent: twelve images cannot carry a decimal."""
    return f"{round(100 * float(value))}%"


def pct_ci(metric: Mapping[str, Any]) -> str:
    """``25% (0 to 50)``: the point estimate never appears without its interval."""
    value = metric.get("value")
    if value is None:
        return "n/a"
    low, high = metric.get("ci_low"), metric.get("ci_high")
    if low is None or high is None:
        return pct(value)
    return f"{pct(value)} ({round(100 * float(low))} to {round(100 * float(high))})"


def count_words(n: int) -> str:
    return _SMALL_NUMBERS[n] if 0 <= n < len(_SMALL_NUMBERS) else str(n)


def _best_recognizer(payload: Mapping[str, Any]) -> tuple[str, Mapping[str, Any]] | None:
    best: tuple[str, Mapping[str, Any]] | None = None
    for name, entry in payload.get("recognizers", {}).items():
        metric = entry.get("metrics", {}).get("exact_match")
        if metric is None:
            continue
        if best is None or float(metric["value"]) > float(best[1]["value"]):
            best = (name, metric)
    return best


@block("ocr-benchmark-status")
def _ocr_benchmark_status(ctx: RenderContext) -> str:
    real = ctx.result("eval_data")
    if real is None:
        return (
            f"**{NO_REAL_BENCHMARK}.** No labelled real evaluation set exists yet, so no "
            "real-world accuracy figure is claimed. `docs/insert_your_own_data.md` explains "
            "where real photos and labels go."
        )
    info = real.get("set", {})
    card = info.get("card") or {}
    photos = card.get("photos", info.get("photos", info.get("n", "?")))
    what = str(card.get("description") or "labelled real photos")
    line = f"[OCR accuracy is benchmarked on {photos} {what}](#real-photos)"
    line += f", with {info.get('n', '?')} readable plates labelled."
    best = _best_recognizer(real)
    if best is not None:
        name, metric = best
        line += (
            f" The best recogniser, {RECOGNIZER_PROSE.get(name, name)}, reads "
            f"{pct_ci(metric)} of those plates exactly from their labelled boxes"
        )
        e2e = (ctx.result("eval_data_e2e") or {}).get("recognizers", {}).get(name, {})
        end_to_end = e2e.get("metrics", {}).get("exact_match")
        if end_to_end is not None:
            line += f" and {pct_ci(end_to_end)} of the photos end to end with the shipped detector"
        line += "."
    if card.get("detector_overlap"):
        line += f" The detector is not independent of these photos: {card['detector_overlap']}."
    line += " The confidence and the conformal sets are still calibrated on synthetic plates."
    return line


def _and_list(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _real_table(payload: Mapping[str, Any]) -> list[str]:
    """One row per recogniser: version and every headline metric with its interval."""
    lines = [
        "| Recogniser | Version | Exact match | Digits | Letter | Region | Character error rate |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, entry in payload.get("recognizers", {}).items():
        metrics = entry.get("metrics", {})
        lines.append(
            f"| {RECOGNIZER_NAMES.get(name, name)} | `{entry.get('model_version', '?')}` | "
            f"{pct_ci(metrics.get('exact_match', {}))} | "
            f"{pct_ci(metrics.get('digits_accuracy', {}))} | "
            f"{pct_ci(metrics.get('letter_accuracy', {}))} | "
            f"{pct_ci(metrics.get('region_accuracy', {}))} | "
            f"{pct_ci(metrics.get('cer', {}))} |"
        )
    return lines


def _letter_note(payload: Mapping[str, Any], unit: str) -> list[str]:
    """``unit`` names what letter and region are scored on, with ``{n}`` for the count."""
    n = int(payload.get("set", {}).get("n", 0))
    letter_n = None
    for entry in payload.get("recognizers", {}).values():
        letter_n = entry.get("metrics", {}).get("letter_accuracy", {}).get("n", letter_n)
    if letter_n is None or letter_n == n:
        return []
    return [
        "",
        f"Letter and region are scored on the {unit.format(n=letter_n)}; a temporary plate has "
        "neither. A lower character error rate is better.",
    ]


def _set_description(real: Mapping[str, Any]) -> list[str]:
    """The set in words and counts, from the results' note and the set card."""
    info = real.get("set", {})
    card = info.get("card") or {}
    note = str(info.get("note") or card.get("description") or "labelled real photos").strip()
    source = info.get("source", "data/eval/labels.csv")
    head = f"Set: data (`{source}`, private and not in the repository): {note}"
    if card.get("photos") is not None:
        head += f", n = {card['photos']} photos holding {card.get('boxes', '?')} labelled plates"
    head += "."
    copies = card.get("copies") or {}
    if copies and card.get("camera_photos") is not None:
        listed = _and_list([f"{count} {what}" for what, count in copies.items()])
        head += (
            f" Every photo is an augmented copy of one of {card['camera_photos']} camera photos "
            f"({listed})"
        )
        head += f"; {card['restored']}." if card.get("restored") else "."
    if card.get("detector_overlap"):
        overlap = str(card["detector_overlap"])
        head += (
            f" {overlap[0].upper()}{overlap[1:]}: the detector has seen these scenes, so the "
            "end-to-end and detector figures below are not independent of its training data; "
            "the recogniser has only ever seen synthetic plates."
        )
    lines = [head]
    transcription = card.get("transcription") or {}
    if transcription:
        excluded = card.get("excluded") or {}
        total = sum(int(v) for v in excluded.values())
        text = (
            f"The plate text was transcribed by eye, crop by crop: {transcription.get('how', '')}. The two "
            f"passes agreed on {transcription.get('agreed', '?')} of "
            f"{transcription.get('crops', '?')} crops, and on all "
            f"{transcription.get('identical_when_both_readable', '?')} where both gave a reading "
            f"the grammar accepts; the third pass accepted "
            f"{transcription.get('accepted_in_third_pass', '?')} of the "
            f"{transcription.get('third_pass', '?')} crops it saw. "
            f"{card.get('text_labels', info.get('n', '?'))} plates in "
            f"{card.get('labelled_photos', info.get('photos', '?'))} photos are labelled "
            f"({card.get('vehicles', '?')} distinct vehicles)"
        )
        if excluded:
            text += f"; {total} were left out: " + _and_list(
                [f"{count} {why}" for why, count in excluded.items()]
            )
        text += (
            ". The benchmark therefore measures plates a person can read, and does not count "
            "the ones left out as failures."
        )
        lines += ["", text]
    return lines


def _bootstrap_sentence(payload: Mapping[str, Any]) -> str:
    boot = payload.get("bootstrap", {})
    level = round(float(boot.get("confidence", 0.95)) * 100)
    if boot.get("unit") == "group":
        return (
            f"Values with {level}% bootstrap intervals that resample the {boot.get('groups', '?')} "
            "vehicle groups (a vehicle with every photo it appears in) instead of single photos, "
            "since copies of one photo and repeat photos of one vehicle are not independent "
            f"({boot.get('resamples', '?')} resamples)."
        )
    return (
        f"Values with {level}% bootstrap intervals over photos "
        f"({boot.get('resamples', '?')} resamples)."
    )


def _detection_sentence(e2e: Mapping[str, Any]) -> str:
    detection = e2e.get("detection") or {}
    missed = int(detection.get("no_detection", e2e.get("set", {}).get("no_detection", 0)) or 0)
    off = int(detection.get("off_plate", 0) or 0)
    if missed:
        text = (
            f"{count_words(missed).capitalize()} photos had no detection and in "
            f"{count_words(off)} more the most confident detection was not on the labelled "
            "plate; both count as wrong reads."
        )
    else:
        text = (
            f"Every photo had a detection; in {count_words(off)} the most confident detection "
            "was not on the labelled plate, which counts as a wrong read."
        )
    if "on_plate" in detection:
        text += (
            f" The most confident detection lay on the labelled plate in "
            f"{pct_ci(detection['on_plate'])} of the photos."
        )
    return text


def _detector_side_by_side(ctx: RenderContext) -> list[str]:
    """The detector on the street photos beside the synthetic scenes: one pass each."""
    real = ctx.result("eval_detector_data")
    synthetic = ctx.result("eval_detector_synthetic")
    if real is None:
        return [
            "The detector on these photos is not measured yet: `uv run plate eval-detector "
            "--data data/eval/detector.yaml`."
        ]
    counts = real.get("counts", {})
    head = (
        f"The detector, measured on {real.get('note') or 'the supplied set'}: "
        f"`models/{real.get('weights', '?')}` at image size {real.get('imgsz', '?')}, one "
        "Ultralytics validation pass, so no interval."
    )
    card = ((ctx.result("eval_data") or {}).get("set", {}).get("card")) or {}
    if card.get("detector_overlap"):
        head += (
            " This column is not an independent measurement of the detector: "
            f"{card['detector_overlap']}."
        )
    real_head = (
        f"Street photos (n = {counts.get('images', '?')} photos, {counts.get('plates', '?')} "
        "plates)"
    )
    lines = [head, ""]
    metrics = real.get("metrics", {})
    if synthetic is None:
        lines += [f"| Metric | {real_head} |", "|---|---|"]
        for key, label in DETECTOR_METRICS:
            lines.append(f"| {label} | {fmt(float(metrics.get(key, 0.0)))} |")
        return lines
    s_counts = synthetic.get("counts", {})
    s_metrics = synthetic.get("metrics", {})
    lines += [
        f"| Metric | {real_head} | Synthetic street scenes (n = {s_counts.get('images', '?')} "
        "scenes) |",
        "|---|---|---|",
    ]
    for key, label in DETECTOR_METRICS:
        lines.append(
            f"| {label} | {fmt(float(metrics.get(key, 0.0)))} | "
            f"{fmt(float(s_metrics.get(key, 0.0)))} |"
        )
    lines += [
        "",
        f"{SYNTHETIC_LABEL.capitalize()}: the synthetic column comes from procedural street "
        "scenes.",
    ]
    return lines


DETECTOR_METRICS: Final = (
    ("precision", "Precision"),
    ("recall", "Recall"),
    ("map50", "mAP@50"),
    ("map50_95", "mAP@50-95"),
)


@block("real-set")
def _real_set(ctx: RenderContext) -> str:
    """The labelled real set in counts and words, for the data card."""
    real = ctx.result("eval_data")
    if real is None:
        return "No labelled real set yet (`docs/insert_your_own_data.md`)."
    lines = [*_set_description(real), "", _bootstrap_sentence(real)]
    e2e = ctx.result("eval_data_e2e")
    if e2e is not None:
        lines += [
            "",
            f"Read end to end, the set is {e2e.get('set', {}).get('n', '?')} photos (every photo "
            "with at least one labelled plate), the labelled boxes ignored.",
        ]
    detector = ctx.result("eval_detector_data")
    if detector is not None:
        counts = detector.get("counts", {})
        lines += [
            "",
            f"The detector is measured on {counts.get('images', '?')} photos holding "
            f"{counts.get('plates', '?')} boxes: {detector.get('note') or 'the supplied set'}.",
        ]
    return "\n".join(lines)


@block("detector-real")
def _detector_real(ctx: RenderContext) -> str:
    return "\n".join(_detector_side_by_side(ctx))


@block("real-photos")
def _real_photos(ctx: RenderContext) -> str:
    real = ctx.result("eval_data")
    if real is None:
        return (
            "No labelled real photos yet: put them under `data/eval` "
            "(`docs/insert_your_own_data.md`) and run `uv run plate eval --set data`."
        )
    info = real.get("set", {})
    n = int(info.get("n", 0))
    note = str(info.get("note") or "").strip()
    lines = _set_description(real)
    lines += ["", _bootstrap_sentence(real), ""]
    lines += [
        f"Read from the labelled box, padded exactly as the service pads a detection (n = {n} "
        f"plates in {info.get('photos', '?')} photos):",
        "",
        *_real_table(real),
        *_letter_note(real, "{n} standard plates"),
    ]
    e2e = ctx.result("eval_data_e2e")
    if e2e is not None:
        e_info = e2e.get("set", {})
        lines += [
            "",
            "Read end to end with the shipped detector, the labelled boxes ignored: the most "
            "confident detection of each photo is cropped exactly as the service crops it "
            f"(n = {e_info.get('n', '?')} photos). {_detection_sentence(e2e)}",
            "",
            *_real_table(e2e),
            *_letter_note(e2e, "{n} photos whose plate is a standard one"),
            "",
            "Exact match side by side:",
            "",
            f"| Recogniser | From the labelled box (n = {n} plates) | End to end (n = "
            f"{e_info.get('n', '?')} photos) |",
            "|---|---|---|",
        ]
        for name, entry in real.get("recognizers", {}).items():
            box = entry.get("metrics", {}).get("exact_match", {})
            whole = e2e.get("recognizers", {}).get(name, {}).get("metrics", {})
            lines.append(
                f"| {RECOGNIZER_NAMES.get(name, name)} | {pct_ci(box)} | "
                f"{pct_ci(whole.get('exact_match', {}))} |"
            )
    else:
        lines += [
            "",
            "End to end with the detector: not measured yet (`uv run plate eval --set data "
            "--detect`).",
        ]
    lines += ["", *_detector_side_by_side(ctx)]
    beam = real.get("recognizers", {}).get("crnn-beam", {}).get("metrics", {})
    calibration = (
        "The calibration remains synthetic. Neither the temperature nor any conformal "
        "threshold was refitted on these photos, which are the reporting set"
    )
    if "ece" in beam and "coverage" in beam:
        calibration += (
            f": the constrained beam's confidence, temperature-scaled on synthetic plates, has "
            f"an expected calibration error of {pct_ci(beam['ece'])} on these plates, and its "
            "conformal sets, whose thresholds were fitted on synthetic splits, hold the true "
            f"plate for {pct_ci(beam['coverage'])} of them"
        )
    calibration += (
        ". A separate real calibration split comes next; until then neither the confidence nor "
        "a set is to be trusted on real photos."
    )
    lines += ["", calibration]
    synthetic = ctx.result("eval_synthetic")
    if synthetic is not None:
        s_n = synthetic.get("set", {}).get("n", "?")
        lines += [
            "",
            "The sim-to-real gap: exact match of the same recognisers on the synthetic test set "
            f"and on the labelled plates. {SYNTHETIC_LABEL.capitalize()}; the synthetic column is "
            "the development harness's, shown only to measure the gap.",
            "",
            f"| Recogniser | Synthetic test set (n = {s_n}) | Real plates (n = {n}) | Gap |",
            "|---|---|---|---|",
        ]
        for name, entry in real.get("recognizers", {}).items():
            r = entry.get("metrics", {}).get("exact_match")
            s_entry = synthetic.get("recognizers", {}).get(name, {})
            s_metric = s_entry.get("metrics", {}).get("exact_match")
            if r is None or s_metric is None:
                continue
            gap = round(100 * (float(s_metric["value"]) - float(r["value"])))
            lines.append(
                f"| {RECOGNIZER_NAMES.get(name, name)} | {pct_ci(s_metric)} | {pct_ci(r)} | "
                f"{gap} points lower on real photos |"
            )
    names = " ".join(f"-r {name}" for name in real.get("recognizers", {}))
    quoted = f' --note "{note}"' if note else ""
    detector_note = str((ctx.result("eval_detector_data") or {}).get("note") or "").strip()
    detector_quoted = f' --note "{detector_note}"' if detector_note else ""
    lines += [
        "",
        f"Reproduce (with the photos in place): `uv run plate eval --set data {names} "
        f"--views 0{quoted}`, the same with `--detect`, and `uv run plate eval-detector --data "
        f"data/eval/detector.yaml{detector_quoted}`.",
    ]
    return "\n".join(lines)


def _recognizer_table(payload: Mapping[str, Any]) -> list[str]:
    lines = [
        "| Recogniser | Version | Exact match | Digits | Letter | Region | CER | ECE | Set coverage |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, entry in payload.get("recognizers", {}).items():
        metrics = entry.get("metrics", {})
        coverage = fmt_ci(metrics["coverage"]) if "coverage" in metrics else "n/a"
        lines.append(
            f"| {name} | `{entry.get('model_version', '?')}` | "
            f"{fmt_ci(metrics.get('exact_match', {}))} | "
            f"{fmt_ci(metrics.get('digits_accuracy', {}))} | "
            f"{fmt_ci(metrics.get('letter_accuracy', {}))} | "
            f"{fmt_ci(metrics.get('region_accuracy', {}))} | "
            f"{fmt_ci(metrics.get('cer', {}))} | "
            f"{fmt_ci(metrics.get('ece', {}))} | {coverage} |"
        )
    lines += [
        "",
        "Set coverage is the share of truths inside the conformal set at the level fixed on the "
        "synthetic conformal split; it holds its level only when the evaluated images are "
        "exchangeable with that split, so a drop on the pseudo-real set is the expected warning "
        "sign of a distribution shift, not a bug.",
    ]
    return lines


def _fusion_table(payload: Mapping[str, Any]) -> list[str]:
    fusion = payload.get("fusion")
    if not fusion:
        return []
    ks = fusion.get("k", [])
    header = "| Recogniser | Fusion | " + " | ".join(f"{k} view(s)" for k in ks) + " |"
    lines = [
        "",
        f"Multi-view sets (exact match of the fused read; n = {fusion.get('n_sets', '?')} sets, "
        "bootstrap over sets):",
        "",
        header,
        "|---|---|" + "---|" * len(ks),
    ]
    for name, entry in fusion.get("recognizers", {}).items():
        for method, by_k in entry.get("methods", {}).items():
            cells = [
                fmt_ci(by_k.get(f"k={k}", {}).get("metrics", {}).get("exact_match", {})) for k in ks
            ]
            lines.append(f"| {name} | {method} | " + " | ".join(cells) + " |")
    return lines


@block("fusion-comparison")
def _fusion_comparison(ctx: RenderContext) -> str:
    payload = ctx.result("eval_views")
    if payload is None or not payload.get("fusion"):
        return (
            "Not measured yet: run `uv run plate eval --set views`. "
            f"{SYNTHETIC_LABEL.capitalize()}."
        )
    fusion = payload["fusion"]
    ks = fusion.get("k", [])
    info = fusion.get("set", {})
    lines = [
        f"**{SYNTHETIC_LABEL.capitalize()}.** Multi-view synthetic sets: n = "
        f"{fusion.get('n_sets', '?')} plates with up to {max(ks) if ks else '?'} views each "
        f"(generator seed {info.get('seed', '?')}); the first k views of every set are fused; "
        "values with bootstrap intervals over sets.",
    ]
    lines += _fusion_table(payload)
    if ks:
        lines += [
            "",
            "Calibration and conformal sets of the fused read (each number of views has its own "
            "threshold, fitted on separate synthetic multi-view sets; see `results/calibration_fused.json`):",
            "",
            "| Recogniser | Fusion | Views | ECE | Set coverage | Mean set size |",
            "|---|---|---|---|---|---|",
        ]
        for name, entry in fusion.get("recognizers", {}).items():
            for method, by_k in entry.get("methods", {}).items():
                for k in sorted({min(ks), max(ks)}):
                    metrics = by_k.get(f"k={k}", {}).get("metrics", {})
                    coverage = fmt_ci(metrics["coverage"]) if "coverage" in metrics else "n/a"
                    size = fmt_ci(metrics["set_size"]) if "set_size" in metrics else "n/a"
                    lines.append(
                        f"| {name} | {method} | {k} | {fmt_ci(metrics.get('ece', {}))} | "
                        f"{coverage} | {size} |"
                    )
    return "\n".join(lines)


def _set_line(payload: Mapping[str, Any]) -> str:
    info = payload.get("set", {})
    boot = payload.get("bootstrap", {})
    level = boot.get("confidence")
    level_text = f"{round(float(level) * 100)}%" if level is not None else "?"
    return (
        f"Set: {info.get('kind', '?')} (`{info.get('name', '?')}`), n = {info.get('n', '?')}, "
        f"generator seed {info.get('seed', '?')}; values with {level_text} bootstrap intervals "
        f"over {boot.get('unit', 'image')}s ({boot.get('resamples', '?')} resamples)."
    )


def _synthetic_block(ctx: RenderContext, result_name: str, command: str) -> str:
    payload = ctx.result(result_name)
    if payload is None:
        return f"Not measured yet: run `{command}`. {SYNTHETIC_LABEL.capitalize()}."
    lines = [f"**{SYNTHETIC_LABEL.capitalize()}.** {_set_line(payload)}", ""]
    lines += _recognizer_table(payload)
    lines += _fusion_table(payload)
    return "\n".join(lines)


@block("synthetic-baseline")
def _synthetic_baseline(ctx: RenderContext) -> str:
    return _synthetic_block(ctx, "eval_synthetic", "uv run plate eval --set synthetic")


@block("pseudo-real-baseline")
def _pseudo_real_baseline(ctx: RenderContext) -> str:
    return _synthetic_block(ctx, "eval_pseudo_real", "uv run plate eval --set pseudo_real")


def _augmentation_text(summary: Mapping[str, Any]) -> str:
    source = summary.get("augment_source") or {}
    multipliers = source.get("multipliers") or {}
    if not multipliers:
        return "the generator's default degradation bounds"
    scaled = ", ".join(f"{group} x{fmt(float(m), 2)}" for group, m in multipliers.items())
    return (
        f"the default bounds scaled as in trial {source.get('trial', '?')} of the augmentation "
        f"sweep ({scaled})"
    )


def _sweep_outcome(ctx: RenderContext, best: Mapping[str, Any]) -> str:
    training = ctx.result("train_crnn") or {}
    trial = (training.get("augment_source") or {}).get("trial")
    if trial is not None and trial == best.get("number"):
        return (
            f"The shipped CRNN is a full training with the configuration of trial {trial}; "
            "its comparison with the weights it replaced follows."
        )
    if ctx.result("crnn_comparison") is not None:
        return (
            "A full training with the best configuration was compared with the shipped weights "
            "and did not replace them; the comparison follows."
        )
    return (
        "The shipped CRNN keeps the default configuration until a full training with the best "
        "one is evaluated."
    )


COMPARISON_SETS: Final = {
    "synthetic": "Synthetic test split (decides)",
    "pseudo_real": "Pseudo-real set (reported only)",
}


@block("crnn-comparison")
def _crnn_comparison(ctx: RenderContext) -> str:
    payload = ctx.result("crnn_comparison")
    if payload is None:
        return (
            "No comparison yet: `uv run plate compare-crnn --old OLD.onnx --new NEW.onnx`. "
            f"{SYNTHETIC_LABEL.capitalize()}."
        )
    old, new = payload.get("old", {}), payload.get("new", {})
    training = new.get("training") or {}
    trial = (training.get("augment_source") or {}).get("trial", "?")
    sets = payload.get("sets", {})
    boot = payload.get("bootstrap", {})
    first: dict[str, Any] = next(iter(sets.values()), {})
    n = first.get("set", {}).get("n", "?")
    how = (
        f"trained from scratch with the shipped recipe, {training.get('epochs', '?')} epochs of "
        f"{training.get('epoch_size', '?')} crops, and the augmentation of sweep trial {trial}"
        if training
        else "the candidate"
    )
    level = fmt(100 * float(boot.get("confidence", 0.95)), 0)
    lines = [
        f"**{SYNTHETIC_LABEL.capitalize()}.** Before: `{old.get('version', '?')}`. Retrained: "
        f"`{new.get('version', '?')}` ({how}). Both read through the grammar-constrained beam "
        f"with their own calibrated temperature, on the same {n} crops per set; differences are "
        f"a paired percentile bootstrap ({boot.get('resamples', '?')} resamples, {level}% "
        "intervals).",
        "",
        "| Set | Before | Retrained | Retrained minus before | Right only before | Right only retrained |",
        "|---|---|---|---|---|---|",
    ]
    for key, entry in sets.items():
        lines.append(
            f"| {COMPARISON_SETS.get(key, key)} | {fmt_ci(entry['old'], 4)} "
            f"| {fmt_ci(entry['new'], 4)} | {fmt_ci(entry['difference'], 4)} "
            f"| {entry.get('only_old_right', '?')} "
            f"| {entry.get('only_new_right', '?')} |"
        )
    verdict = (
        "the retrained weights replaced the previous ones, which stay in the registry as history"
        if payload.get("adopt")
        else "the previous weights stay in service; the retrained ones are not committed, and the "
        "shipped CRNN, its calibration and every other result are unchanged"
    )
    lines += [
        "",
        f"The rule, fixed before the comparison ran: {payload.get('rule', '?')}. "
        f"Outcome: {verdict}.",
    ]
    return "\n".join(lines)


@block("crnn-training")
def _crnn_training(ctx: RenderContext) -> str:
    summary = ctx.result("train_crnn")
    if summary is None:
        return "Not trained yet: run `uv run plate train crnn`."
    config = summary.get("config", {})
    onnx = ctx.root / "models" / "crnn.onnx"
    size = f"{onnx.stat().st_size / 1e6:.1f} MB" if onnx.exists() else "missing"
    epochs = config.get("epochs", "?")
    per_epoch = config.get("epoch_size", "?")
    return "\n".join(
        [
            f"`models/crnn.onnx` (version `{summary.get('model_version', '?')}`, {size}, "
            f"{summary.get('parameters', '?')} parameters): trained on synthetic crops only, "
            f"{epochs} epochs of {per_epoch} freshly generated crops each on `{summary.get('device', '?')}`, "
            f"in {summary.get('seconds', '?')} s. The kept epoch is {summary.get('best_epoch', '?')}, "
            "chosen by greedy exact match on the synthetic validation split "
            f"({fmt(float(summary.get('best_val_exact_greedy', 0.0)))}). "
            f"Fine-tuned on real data: {'yes' if summary.get('fine_tuned_on_real_data') else 'no'}. "
            f"Augmentation: {_augmentation_text(summary)}. "
            f"{SYNTHETIC_LABEL.capitalize()}.",
        ]
    )


@block("augmentation-sweep")
def _augmentation_sweep(ctx: RenderContext) -> str:
    payload = ctx.result("sweep")
    if payload is None:
        return f"Not run yet: `uv run plate sweep`. {SYNTHETIC_LABEL.capitalize()}."
    budget = payload.get("budget", {})
    groups = list(payload.get("groups", {}))
    baseline = payload.get("baseline", {})
    best = payload.get("best", {})
    lines = [
        f"**{SYNTHETIC_LABEL.capitalize()}.** {len(payload.get('trials', []))} trials, each "
        + (
            f"fine-tuning `{payload['init_weights']}` for "
            if payload.get("init_weights")
            else "training from scratch for "
        )
        + f"{budget.get('epochs', '?')} epochs of {budget.get('epoch_size', '?')} synthetic crops "
        f"on `{budget.get('device', '?')}`, scored by greedy exact match on "
        f"{budget.get('tune_size', '?')} pseudo-real tuning crops (seed "
        f"{payload.get('splits', {}).get('tuning', {}).get('seed', '?')}) with 95% "
        "bootstrap intervals; trial "
        f"{baseline.get('number', '?')} is the default configuration, and differences are "
        "paired against it over the same crops. "
        + (
            f"The weights the trials started from score "
            f"{fmt_ci(payload['shipped_before_fine_tuning'])} before any fine-tuning. "
            if payload.get("shipped_before_fine_tuning")
            else ""
        )
        + _sweep_outcome(ctx, best),
        "",
        "| Trial | "
        + " | ".join(groups)
        + " | Pseudo-real exact match | Difference to the shipped configuration | "
        "Synthetic validation |",
        "|---|" + "---|" * len(groups) + "---|---|---|",
    ]
    trials = sorted(
        payload.get("trials", []),
        key=lambda t: (-float(t["pseudo_real_exact_greedy"]), int(t["number"])),
    )
    for trial in trials:
        tag = ""
        if trial.get("number") == best.get("number"):
            tag = " (best)"
        elif trial.get("number") == baseline.get("number"):
            tag = " (default)"
        multipliers = trial.get("multipliers", {})
        low_high = trial.get("pseudo_real_ci")
        score = fmt(float(trial["pseudo_real_exact_greedy"]))
        if low_high:
            score += f" [{fmt(float(low_high[0]))}, {fmt(float(low_high[1]))}]"
        difference = trial.get("difference_vs_trial_0")
        paired = (
            "reference"
            if trial.get("number") == baseline.get("number")
            else (fmt_ci(difference) if difference else "n/a")
        )
        lines.append(
            f"| {trial['number']}{tag} | "
            + " | ".join(fmt(float(multipliers.get(g, 1.0)), 2) for g in groups)
            + f" | {score} | {paired}"
            f" | {fmt(float(trial['synthetic_val_exact_greedy']))} |"
        )
    return "\n".join(lines)


@block("cv-evidence")
def _cv_evidence(ctx: RenderContext) -> str:
    """The figures behind docs/CV_NOTES.md, each with the results file it comes from."""
    rows: list[tuple[str, str, str]] = []

    real = ctx.result("eval_data")
    if real is not None:
        n = real.get("set", {}).get("n", "?")
        for name, claim in (
            (
                "crnn-beam",
                f"CRNN (constrained beam), exact match on {n} labelled real plates, from the box",
            ),
            ("easyocr", "EasyOCR baseline, exact match on the same real plates"),
        ):
            metric = real.get("recognizers", {}).get(name, {}).get("metrics", {}).get("exact_match")
            if metric is not None:
                rows.append((claim, fmt_ci(metric), "`results/eval_data.json`"))
    e2e = ctx.result("eval_data_e2e")
    if e2e is not None:
        n_photos = e2e.get("set", {}).get("n", "?")
        beam = e2e.get("recognizers", {}).get("crnn-beam", {}).get("metrics", {})
        if "exact_match" in beam:
            rows.append(
                (
                    f"CRNN (constrained beam), exact match end to end on {n_photos} real photos "
                    "with the shipped detector",
                    fmt_ci(beam["exact_match"]),
                    "`results/eval_data_e2e.json`",
                )
            )
    real_detector = ctx.result("eval_detector_data")
    if real_detector is not None:
        metrics = real_detector.get("metrics", {})
        rows.append(
            (
                "Detector mAP@50 and mAP@50-95 on the real photos (one pass, no interval; the "
                "detector has seen these scenes)",
                f"{fmt(float(metrics.get('map50', 0.0)))} and "
                f"{fmt(float(metrics.get('map50_95', 0.0)))}",
                "`results/eval_detector_data.json`",
            )
        )

    synthetic = ctx.result("eval_synthetic")
    pseudo = ctx.result("eval_pseudo_real")
    if synthetic is not None:
        recognizers = synthetic.get("recognizers", {})
        beam = recognizers.get("crnn-beam", {}).get("metrics", {})
        easy = recognizers.get("easyocr", {}).get("metrics", {})
        if "exact_match" in beam:
            rows.append(
                (
                    "CRNN (constrained beam), exact match on the synthetic test set",
                    fmt_ci(beam["exact_match"]),
                    "`results/eval_synthetic.json`",
                )
            )
        if "exact_match" in easy:
            rows.append(
                (
                    "EasyOCR baseline, exact match on the same set",
                    fmt_ci(easy["exact_match"]),
                    "`results/eval_synthetic.json`",
                )
            )
        if "ece" in beam:
            rows.append(
                (
                    "CRNN (constrained beam), expected calibration error",
                    fmt_ci(beam["ece"]),
                    "`results/eval_synthetic.json`",
                )
            )
        fusion = synthetic.get("fusion", {}).get("recognizers", {}).get("crnn-beam", {})
        methods = fusion.get("methods", {}).get("probabilistic", {})
        ks = synthetic.get("fusion", {}).get("k", [])
        if ks and f"k={ks[-1]}" in methods:
            rows.append(
                (
                    f"CRNN, exact match of the probabilistic fusion of {ks[-1]} views",
                    fmt_ci(methods[f"k={ks[-1]}"]["metrics"]["exact_match"]),
                    "`results/eval_synthetic.json`",
                )
            )
    calibration = ctx.result("calibration_crnn")
    if calibration is not None:
        coverage = calibration.get("conformal", {}).get("coverage", {})
        for alpha in sorted(coverage, key=float):
            report = coverage[alpha]
            rows.append(
                (
                    f"Conformal sets at level {fmt(float(report['level']), 2)}, measured coverage",
                    fmt_ci(report["coverage"]),
                    "`results/calibration_crnn.json`",
                )
            )
    fused = ctx.result("calibration_fused")
    if fused is not None:
        coverage = fused.get("coverage", {})
        views = sorted(coverage, key=int)
        if views:
            top = coverage[views[-1]]
            alpha = sorted(top, key=float)[0]
            report = top[alpha]
            rows.append(
                (
                    f"Fused sets over {views[-1]} views at level {fmt(float(report['level']), 2)}, "
                    "measured coverage",
                    fmt_ci(report["coverage"]),
                    "`results/calibration_fused.json`",
                )
            )
    if synthetic is not None and pseudo is not None:
        a = synthetic.get("recognizers", {}).get("crnn-beam", {}).get("metrics", {})
        b = pseudo.get("recognizers", {}).get("crnn-beam", {}).get("metrics", {})
        if "exact_match" in a and "exact_match" in b:
            rows.append(
                (
                    "CRNN (constrained beam), exact match on the pseudo-real set",
                    fmt_ci(b["exact_match"]),
                    "`results/eval_pseudo_real.json`",
                )
            )
    sweep = ctx.result("sweep")
    if sweep is not None:
        best = sweep.get("best", {})
        rows.append(
            (
                f"Augmentation sweep, best of {len(sweep.get('trials', []))} trials on the "
                "pseudo-real tuning split",
                fmt(float(best.get("pseudo_real_exact_greedy", 0.0))),
                "`results/sweep.json`",
            )
        )
    detector = ctx.result("eval_detector_synthetic")
    if detector is not None:
        metrics = detector.get("metrics", {})
        rows.append(
            (
                "Detector mAP@50 and mAP@50-95 on synthetic street scenes (one pass, no interval)",
                f"{fmt(float(metrics.get('map50', 0.0)))} and "
                f"{fmt(float(metrics.get('map50_95', 0.0)))}",
                "`results/eval_detector_synthetic.json`",
            )
        )
    comparison = ctx.result("crnn_comparison")
    if comparison is not None:
        for key, claim in (
            (
                "synthetic",
                "Retrained CRNN minus the previous weights, exact match on the synthetic test split",
            ),
            ("pseudo_real", "The same paired difference on the pseudo-real set"),
        ):
            entry = comparison.get("sets", {}).get(key)
            if entry is not None:
                rows.append(
                    (claim, fmt_ci(entry["difference"], 4), "`results/crnn_comparison.json`")
                )
    training = ctx.result("train_crnn")
    if training is not None:
        rows.append(
            (
                "CRNN parameters",
                str(training.get("parameters", "?")),
                "`results/train_crnn.json`",
            )
        )
    if not rows:
        return f"No results yet. {SYNTHETIC_LABEL.capitalize()}."
    lines = [
        f"**{SYNTHETIC_LABEL.capitalize()}.** Every row is synthetic except those from "
        "`results/eval_data.json`, `results/eval_data_e2e.json` and "
        "`results/eval_detector_data.json`, which are real photos. Values with 95% bootstrap "
        "intervals where the source records one.",
        "",
        "| Claim | Value | Source |",
        "|---|---|---|",
    ]
    lines += [f"| {claim} | {value} | {source} |" for claim, value, source in rows]
    return "\n".join(lines)


@block("fused-calibration")
def _fused_calibration(ctx: RenderContext) -> str:
    payload = ctx.result("calibration_fused")
    if payload is None:
        return f"Not calibrated yet: run `uv run plate train calibrate-fused`. {SYNTHETIC_LABEL.capitalize()}."
    splits = payload.get("splits", {})
    lines = [
        f"**{SYNTHETIC_LABEL.capitalize()}.** Model `{payload.get('model_version', '?')}`; "
        f"thresholds fitted on {splits.get('calibration', {}).get('n_sets', '?')} synthetic "
        f"multi-view calibration sets (seed {splits.get('calibration', {}).get('seed', '?')}), "
        f"coverage measured on {splits.get('test', {}).get('n_sets', '?')} separate sets with a "
        "joint bootstrap; real multi-photo data must refit them.",
        "",
        "| Views | Level | Threshold | Coverage | Mean set size | Empty sets |",
        "|---|---|---|---|---|---|",
    ]
    for views, by_alpha in payload.get("coverage", {}).items():
        for _, report in sorted(by_alpha.items(), reverse=True):
            level = f"{round(float(report['level']) * 100)}%"
            lines.append(
                f"| {views} | {level} | `{float(report['threshold']):.2e}` | "
                f"{fmt_ci(report['coverage'])} | {fmt_ci(report['set_size'])} | "
                f"{fmt(float(report['empty_rate']))} |"
            )
    return "\n".join(lines)


@block("crnn-calibration")
def _crnn_calibration(ctx: RenderContext) -> str:
    payload = ctx.result("calibration_crnn")
    if payload is None:
        return "Not calibrated yet: run `uv run plate train calibrate`."
    temp = payload.get("temperature", {})
    splits = payload.get("splits", {})
    before = payload.get("calibration_split", {}).get("before", {})
    after = payload.get("calibration_split", {}).get("after", {})
    test = payload.get("test_split", {})
    lines = [
        f"**{SYNTHETIC_LABEL.capitalize()}.** Model `{payload.get('model_version', '?')}`; "
        f"temperature fitted on the synthetic calibration split "
        f"(n = {splits.get('calibration', {}).get('n', '?')}): "
        f"T = {fmt(float(temp.get('temperature', float('nan'))))}, "
        f"NLL of the true plate {fmt(float(temp.get('nll_before', float('nan'))))} at T = 1 "
        f"and {fmt(float(temp.get('nll_after', float('nan'))))} after.",
        "",
        "| Split | Exact match | Mean confidence | ECE |",
        "|---|---|---|---|",
        f"| calibration, T = 1 | {fmt_ci(before.get('exact_match', {}))} | "
        f"{fmt_ci(before.get('mean_confidence', {}))} | {fmt_ci(before.get('ece', {}))} |",
        f"| calibration, fitted T | {fmt_ci(after.get('exact_match', {}))} | "
        f"{fmt_ci(after.get('mean_confidence', {}))} | {fmt_ci(after.get('ece', {}))} |",
        f"| test, fitted T | {fmt_ci(test.get('exact_match', {}))} | "
        f"{fmt_ci(test.get('mean_confidence', {}))} | {fmt_ci(test.get('ece', {}))} |",
        "",
        "Conformal prediction sets (thresholds from the conformal split, "
        f"n = {splits.get('conformal', {}).get('n', '?')}; coverage measured on the test split, "
        f"n = {splits.get('test', {}).get('n', '?')}, with a joint bootstrap over both splits):",
        "",
        "| Level | Coverage | Mean set size | Singleton sets |",
        "|---|---|---|---|",
    ]
    for _, report in sorted(payload.get("conformal", {}).get("coverage", {}).items(), reverse=True):
        level = f"{round(float(report['level']) * 100)}%"
        lines.append(
            f"| {level} | {fmt_ci(report['coverage'])} | {fmt_ci(report['set_size'])} | "
            f"{fmt(float(report['singleton_rate']))} |"
        )
    return "\n".join(lines)


# --- render and check -------------------------------------------------------------
def render_text(text: str, ctx: RenderContext, path: str = "<text>") -> tuple[str, list[Problem]]:
    problems: list[Problem] = []
    opened = [m.group("name") for m in _OPEN_RE.finditer(text)]
    closed = [m.group("name") for m in _BLOCK_RE.finditer(text)]
    for name in opened:
        if opened.count(name) != closed.count(name):
            problems.append(Problem(path, f"block {name!r} is not closed"))

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        renderer = BLOCKS.get(name)
        if renderer is None:
            problems.append(Problem(path, f"unknown render block {name!r}"))
            return match.group(0)
        body = renderer(ctx).rstrip("\n") + "\n"
        return f"<!-- BEGIN RENDER {name} -->\n{body}<!-- END RENDER {name} -->"

    return _BLOCK_RE.sub(replace, text), problems


def _prose(text: str) -> str:
    """Text outside render blocks, code and comments: where a hand-typed number hides."""
    text = _BLOCK_RE.sub("", text)
    text = _FENCE_RE.sub("", text)
    text = _COMMENT_RE.sub("", text)
    return _INLINE_CODE_RE.sub("", text)


def find_hand_typed(text: str) -> list[str]:
    return [m.group(0) for m in _METRIC_RE.finditer(_prose(text))]


def check_text(text: str, ctx: RenderContext, path: str = "<text>") -> list[Problem]:
    rendered, problems = render_text(text, ctx, path)
    if rendered != text:
        diff = "".join(
            difflib.unified_diff(
                text.splitlines(keepends=True),
                rendered.splitlines(keepends=True),
                fromfile=f"{path} (committed)",
                tofile=f"{path} (rendered)",
                n=1,
            )
        )
        problems.append(Problem(path, "rendered blocks drifted from their sources:\n" + diff))
    for number in find_hand_typed(text):
        problems.append(Problem(path, f"hand-typed metric-like number {number!r} outside a block"))
    lowered = text.lower()
    names = {m.group("name") for m in _BLOCK_RE.finditer(text)}
    if names & {"synthetic-baseline", "pseudo-real-baseline"} and SYNTHETIC_LABEL not in lowered:
        problems.append(
            Problem(path, f"synthetic metrics without the sentence {SYNTHETIC_LABEL!r}")
        )
    if (
        path.endswith("README.md")
        and ctx.result("eval_data") is None
        and NO_REAL_BENCHMARK not in text
    ):
        problems.append(Problem(path, f"the statement {NO_REAL_BENCHMARK!r} must stay"))
    return problems


def governed_paths(root: Path, files: Iterable[str] | None = None) -> list[Path]:
    names = list(files) if files is not None else list(GOVERNED_FILES)
    return [root / name for name in names if (root / name).exists()]


def render_files(root: Path = PROJECT_ROOT, files: Iterable[str] | None = None) -> list[Problem]:
    ctx = RenderContext(root=root)
    problems: list[Problem] = []
    for path in governed_paths(root, files):
        text = path.read_text(encoding="utf-8")
        rendered, found = render_text(text, ctx, str(path.relative_to(root)))
        problems.extend(found)
        if rendered != text:
            path.write_text(rendered, encoding="utf-8", newline="\n")
    return problems


def check_files(root: Path = PROJECT_ROOT, files: Iterable[str] | None = None) -> list[Problem]:
    ctx = RenderContext(root=root)
    problems: list[Problem] = []
    for path in governed_paths(root, files):
        text = path.read_text(encoding="utf-8")
        problems.extend(check_text(text, ctx, str(path.relative_to(root)).replace("\\", "/")))
    return problems


__all__ = [
    "BLOCKS",
    "GOVERNED_FILES",
    "NO_REAL_BENCHMARK",
    "SYNTHETIC_LABEL",
    "Problem",
    "RenderContext",
    "best_detector_epoch",
    "check_files",
    "check_text",
    "find_hand_typed",
    "render_files",
    "render_text",
    "ultralytics_fitness",
]
