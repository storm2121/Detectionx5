"""Write synthetic sets to disk in the same layouts as the real-data placeholder.

Crops and the pseudo-real set use the ``data/ocr`` layout (``labels.csv`` with
``crop_path,plate_text,format``), scenes use the YOLO layout of ``data/detector`` plus an
``eval``-style ``labels.csv``, so every tool that reads real data reads synthetic data
unchanged. The manifest carries no timestamp: a seed reproduces every byte, including the
manifest, and its ``digest`` summarises all written files.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

import cv2

from ..docs_render import SYNTHETIC_LABEL
from ..grammar import GRAMMAR, to_display
from ..imaging import Image
from . import augment as aug
from .generate import (
    GENERATOR_VERSION,
    CropSample,
    make_crop,
    make_pseudo_real,
    make_scene,
    make_views,
)

SetKind = Literal["crops", "pseudo_real", "views", "scenes"]
PNG_PARAMS: Final = [cv2.IMWRITE_PNG_COMPRESSION, 6]


def encode_png(image: Image) -> bytes:
    """PNG bytes with fixed parameters and no metadata chunks: identical pixels, identical bytes."""
    ok, encoded = cv2.imencode(".png", image, PNG_PARAMS)
    if not ok:  # pragma: no cover - OpenCV always encodes uint8 images
        raise RuntimeError("PNG encoding failed")
    return encoded.tobytes()


@dataclass(frozen=True)
class Manifest:
    kind: SetKind
    seed: int
    n: int
    digest: str
    path: Path

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "seed": self.seed, "n": self.n, "digest": self.digest}


def _digest(root: Path, files: Iterable[Path]) -> str:
    total = hashlib.sha256()
    for path in sorted(files):
        total.update(path.relative_to(root).as_posix().encode())
        total.update(hashlib.sha256(path.read_bytes()).digest())
    return total.hexdigest()


def _write_manifest(
    out: Path, kind: SetKind, seed: int, n: int, files: list[Path], extra: dict[str, Any]
) -> Manifest:
    digest = _digest(out, files)
    payload = {
        "generator": "detectionx5.synthetic",
        "generator_version": GENERATOR_VERSION,
        "kind": kind,
        "set_kind": "pseudo_real" if kind == "pseudo_real" else "synthetic",
        "label": SYNTHETIC_LABEL,
        "seed": seed,
        "n": n,
        "digest": digest,
        **extra,
    }
    path = out / "manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return Manifest(kind=kind, seed=seed, n=n, digest=digest, path=path)


def _write_csv(path: Path, header: tuple[str, ...], rows: Iterable[tuple[object, ...]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _save(path: Path, image: Image) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_png(image))
    return path


def write_crops(
    out: Path,
    n: int,
    seed: int,
    *,
    pseudo_real: bool = False,
    progress: Callable[[int], object] | None = None,
) -> Manifest:
    """``n`` labelled crops in the ``data/ocr`` layout."""
    out.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    rows: list[tuple[object, ...]] = []
    meta_lines: list[str] = []
    for index in range(n):
        sample: CropSample = (
            make_pseudo_real(seed, index) if pseudo_real else make_crop(seed, index)
        )
        name = f"crops/{index:06d}.png"
        files.append(_save(out / name, sample.image))
        rows.append((name, sample.text, sample.format))
        meta_lines.append(json.dumps({"crop_path": name, **sample.meta}, sort_keys=True))
        if progress:
            progress(index + 1)
    _write_csv(out / "labels.csv", ("crop_path", "plate_text", "format"), rows)
    (out / "meta.jsonl").write_text("\n".join(meta_lines) + "\n", encoding="utf-8")
    files += [out / "labels.csv", out / "meta.jsonl"]
    config = aug.PSEUDO_REAL if pseudo_real else aug.DEFAULT
    kind: SetKind = "pseudo_real" if pseudo_real else "crops"
    return _write_manifest(out, kind, seed, n, files, {"augment": config.as_dict()})


def write_views(
    out: Path,
    n_sets: int,
    k: int,
    seed: int,
    *,
    progress: Callable[[int], object] | None = None,
) -> Manifest:
    """``n_sets`` plates, each photographed ``k`` times under independent conditions."""
    out.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    rows: list[tuple[object, ...]] = []
    for index in range(n_sets):
        for view, sample in enumerate(make_views(seed, index, k), start=1):
            name = f"views/{index:05d}_{view}.png"
            files.append(_save(out / name, sample.image))
            rows.append(
                (
                    index,
                    view,
                    name,
                    sample.text,
                    sample.format,
                    f"{sample.meta['strength']:.6f}",
                    f"{sample.meta['sharpness']:.6f}",
                )
            )
        if progress:
            progress(index + 1)
    header = ("set_id", "view", "image_path", "plate_text", "format", "strength", "sharpness")
    _write_csv(out / "views.csv", header, rows)
    files.append(out / "views.csv")
    return _write_manifest(out, "views", seed, n_sets, files, {"k": k})


def write_scenes(
    out: Path,
    n: int,
    seed: int,
    *,
    val_fraction: float = 0.2,
    progress: Callable[[int], object] | None = None,
) -> Manifest:
    """Scenes as a complete stand-in for ``data/``: detector layout plus ``eval/labels.csv``.

    ``plate data validate --root <out>`` therefore checks a synthetic scene set with exactly
    the rules real data must pass, and ``plate eval --set data`` can run end to end on it.
    """
    out.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    eval_rows: list[tuple[object, ...]] = []
    n_val = round(n * val_fraction)
    for index in range(n):
        split = "val" if index < n_val else "train"
        sample = make_scene(seed, index)
        h, w = sample.image.shape[:2]
        image_name = f"detector/images/{split}/{index:06d}.png"
        files.append(_save(out / image_name, sample.image))
        lines = []
        for tokens, (x1, y1, x2, y2) in sample.plates:
            cx, cy = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h
            bw, bh = (x2 - x1) / w, (y2 - y1) / h
            lines.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
            fmt = GRAMMAR.format_of(tokens) or "standard"
            eval_rows.append((f"../{image_name}", to_display(tokens), fmt, x1, y1, x2, y2))
        label_path = out / f"detector/labels/{split}/{index:06d}.txt"
        label_path.parent.mkdir(parents=True, exist_ok=True)
        label_path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        files.append(label_path)
        if progress:
            progress(index + 1)
    yaml_text = "train: detector/images/train\nval: detector/images/val\nnames:\n  0: LP\n"
    (out / "detector.yaml").write_text(yaml_text, encoding="utf-8")
    (out / "eval").mkdir(exist_ok=True)
    header = ("image_path", "plate_text", "format", "x1", "y1", "x2", "y2")
    _write_csv(out / "eval" / "labels.csv", header, eval_rows)
    files += [out / "detector.yaml", out / "eval" / "labels.csv"]
    return _write_manifest(out, "scenes", seed, n, files, {"val_fraction": val_fraction})


__all__ = ["Manifest", "encode_png", "write_crops", "write_scenes", "write_views"]
