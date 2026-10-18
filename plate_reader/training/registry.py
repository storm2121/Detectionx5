"""The model registry, ``models/registry.json``.

Promoting a version records what is known about it at that moment: which file it is, the
metrics every committed results file reports for it (each with its set kind), the
fingerprint of the data it was trained on, and when. The service serves the registry at
``GET /models``; the dashboard's Models page (M5) reads it from there.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from ..crnn.runtime import file_version
from ..synthetic.generate import GENERATOR_VERSION
from ..synthetic.splits import SPLIT_SEEDS

SCHEMA: Final = "detectionx5.registry/1"
CANDIDATES: Final = {"crnn": "crnn.onnx", "detector": "detector.onnx", "detector-pt": "best.pt"}


def _load(path: Path) -> dict[str, Any]:
    if path.exists():
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
    return {"schema": SCHEMA, "models": [], "active": {}}


def data_fingerprint(data_dir: Path) -> str:
    """Hash of the real OCR labels when they exist, else the synthetic recipe."""
    labels = data_dir / "ocr" / "train" / "labels.csv"
    if labels.exists() and labels.stat().st_size > 0:
        return "data:" + hashlib.sha256(labels.read_bytes()).hexdigest()[:16]
    return f"synthetic:generator-{GENERATOR_VERSION}:train-seed-{SPLIT_SEEDS['train']}"


def _metrics_for(version: str, results_dir: Path) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for path in sorted(results_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        kind = payload.get("set", {}).get("kind")
        for name, entry in payload.get("recognizers", {}).items():
            if version in str(entry.get("model_version", "")):
                metrics = entry.get("metrics", {})
                found[f"{path.stem}/{name}"] = {
                    "set_kind": kind,
                    "n": entry.get("n"),
                    "exact_match": metrics.get("exact_match"),
                    "cer": metrics.get("cer"),
                    "ece": metrics.get("ece"),
                }
        if payload.get("model_version") == version and "conformal" in payload:
            found[path.stem] = {
                "set_kind": payload.get("set", {}).get("kind", "synthetic"),
                "coverage": {a: r["coverage"] for a, r in payload["conformal"]["coverage"].items()},
            }
    return found


def find_model(version: str, models_dir: Path) -> tuple[str, Path]:
    for kind, name in CANDIDATES.items():
        path = models_dir / name
        if path.exists() and file_version(path) == version:
            return kind.removesuffix("-pt"), path
    raise KeyError(f"no model with version {version!r} under {models_dir}")


def promote(
    version: str,
    models_dir: Path,
    results_dir: Path,
    data_dir: Path,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    kind, path = find_model(version, models_dir)
    registry_path = registry_path or models_dir / "registry.json"
    registry = _load(registry_path)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    entry = {
        "kind": kind,
        "version": version,
        "file": path.name,
        "bytes": path.stat().st_size,
        "metrics": _metrics_for(version, results_dir),
        "data_fingerprint": data_fingerprint(data_dir),
        "created_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(
            timespec="seconds"
        ),
        "promoted_at": now,
    }
    registry["models"] = [m for m in registry["models"] if m.get("version") != version] + [entry]
    registry.setdefault("active", {})[kind] = version
    registry_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return entry


def listing(registry_path: Path) -> dict[str, Any]:
    return _load(registry_path)


__all__ = ["SCHEMA", "data_fingerprint", "find_model", "listing", "promote"]
