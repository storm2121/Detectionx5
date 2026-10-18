"""A self-contained HTML report (Plotly) next to each results JSON.

The report is regenerated on every evaluation and never committed (``results/*.html`` is
ignored); the JSON is the source of truth. Plotly's script is inlined once so the report
opens offline.
"""

from __future__ import annotations

import html
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

METRIC_LABELS = {
    "exact_match": "Exact match",
    "digits_accuracy": "Digits",
    "letter_accuracy": "Letter",
    "region_accuracy": "Region",
    "read_rate": "Read rate",
    "cer": "CER",
    "ece": "ECE",
}


def _bar_with_ci(payload: Mapping[str, Any]) -> go.Figure:
    figure = go.Figure()
    for name, entry in payload.get("recognizers", {}).items():
        keys = [k for k in METRIC_LABELS if k in entry["metrics"]]
        values = [entry["metrics"][k]["value"] or 0.0 for k in keys]
        upper = [
            (entry["metrics"][k]["ci_high"] or 0.0) - v for k, v in zip(keys, values, strict=True)
        ]
        lower = [
            v - (entry["metrics"][k]["ci_low"] or 0.0) for k, v in zip(keys, values, strict=True)
        ]
        figure.add_trace(
            go.Bar(
                name=name,
                x=[METRIC_LABELS[k] for k in keys],
                y=values,
                error_y={"type": "data", "array": upper, "arrayminus": lower},
            )
        )
    figure.update_layout(
        barmode="group", title="Metrics with 95% bootstrap intervals", yaxis_range=[0, 1]
    )
    return figure


def _reliability(payload: Mapping[str, Any]) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="perfect", line={"dash": "dot"})
    )
    for name, entry in payload.get("recognizers", {}).items():
        bins = [b for b in entry["reliability"] if b["n"]]
        figure.add_trace(
            go.Scatter(
                x=[b["confidence"] for b in bins],
                y=[b["accuracy"] for b in bins],
                mode="lines+markers",
                name=name,
                text=[f"n={b['n']}" for b in bins],
            )
        )
    figure.update_layout(
        title="Reliability (top-prediction confidence vs accuracy)",
        xaxis_title="confidence",
        yaxis_title="accuracy",
    )
    return figure


def _confusions(payload: Mapping[str, Any]) -> list[go.Figure]:
    figures = []
    for name, entry in payload.get("recognizers", {}).items():
        confusion = entry["letter_confusion"]
        figure = go.Figure(
            go.Heatmap(
                z=confusion["matrix"],
                x=confusion["columns"],
                y=confusion["rows"],
                colorscale="Blues",
            )
        )
        figure.update_layout(title=f"Letter confusion: {name} (rows truth, columns prediction)")
        figures.append(figure)
    return figures


def _fusion(payload: Mapping[str, Any]) -> go.Figure | None:
    fusion = payload.get("fusion")
    if not fusion:
        return None
    figure = go.Figure()
    for name, entry in fusion["recognizers"].items():
        for method, by_k in entry["methods"].items():
            ks = [int(key.split("=")[1]) for key in by_k]
            values = [by_k[f"k={k}"]["metrics"]["exact_match"]["value"] for k in ks]
            low = [by_k[f"k={k}"]["metrics"]["exact_match"]["ci_low"] for k in ks]
            high = [by_k[f"k={k}"]["metrics"]["exact_match"]["ci_high"] for k in ks]
            figure.add_trace(
                go.Scatter(
                    x=ks,
                    y=values,
                    mode="lines+markers",
                    name=f"{name} / {method}",
                    error_y={
                        "type": "data",
                        "array": [h - v for h, v in zip(high, values, strict=True)],
                        "arrayminus": [v - lo for v, lo in zip(values, low, strict=True)],
                    },
                )
            )
    figure.update_layout(
        title="Exact match versus number of views", xaxis_title="views", yaxis_title="exact match"
    )
    return figure


def write_report(payload: Mapping[str, Any], path: Path) -> Path:
    figures = [_bar_with_ci(payload), _reliability(payload), *_confusions(payload)]
    fusion = _fusion(payload)
    if fusion is not None:
        figures.append(fusion)
    parts = []
    for index, figure in enumerate(figures):
        parts.append(figure.to_html(full_html=False, include_plotlyjs=index == 0))
    info = payload.get("set", {})
    label = payload.get("label")
    banner = f"<p><strong>{html.escape(label.capitalize())}.</strong></p>" if label else ""
    body = "\n".join(parts)
    document = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Evaluation report</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem}</style>"
        "</head><body>"
        f"<h1>Evaluation: {html.escape(str(info.get('name', '?')))}</h1>{banner}"
        f"<p>Set kind {html.escape(str(info.get('kind')))}, n = {info.get('n')}.</p>{body}</body></html>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
    return path


__all__ = ["write_report"]
