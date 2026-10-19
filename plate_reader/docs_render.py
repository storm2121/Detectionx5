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


@block("ocr-benchmark-status")
def _ocr_benchmark_status(ctx: RenderContext) -> str:
    real = ctx.result("eval_data")
    if real is None:
        return (
            f"**{NO_REAL_BENCHMARK}.** No labelled real evaluation set exists yet, so no "
            "real-world accuracy figure is claimed. `docs/insert_your_own_data.md` explains "
            "where real photos and labels go."
        )
    n = real.get("set", {}).get("n", "?")
    return f"OCR accuracy is benchmarked on a labelled real set of {n} images (see below)."


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
        f"{baseline.get('number', '?')} is the shipped configuration, and differences are "
        "paired against it over the same crops. "
        + (
            f"The shipped weights score {fmt_ci(payload['shipped_before_fine_tuning'])} "
            "before any fine-tuning. "
            if payload.get("shipped_before_fine_tuning")
            else ""
        )
        + (
            "The best configuration is in use."
            if payload.get("adopted")
            else "The shipped CRNN keeps the default configuration until a full training with "
            "the best one is evaluated."
        ),
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
            tag = " (shipped)"
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
