#!/usr/bin/env python
"""Command-line entry point (compatibility shim for ``plate read``).

    python cli.py samples/car.jpg
    python cli.py photo1.jpg photo2.jpg --save-crops
    python cli.py samples/car.jpg --json

The implementation lives in :mod:`plate_reader.cli.read`; this file keeps the original
argparse interface and exit codes so existing scripts and the README stay true.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import config
from plate_reader import available_backends
from plate_reader.cli.read import as_dict, run, save_crops


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Detect and read Moroccan licence plates. Runs fully offline.",
    )
    parser.add_argument("images", nargs="+", type=Path, help="one or more image files")
    parser.add_argument(
        "--model",
        type=Path,
        default=config.MODEL_PATH,
        help="path to YOLO weights (default: models/best.pt)",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=config.DETECTION_CONF,
        help=f"detection confidence threshold (default: {config.DETECTION_CONF})",
    )
    parser.add_argument(
        "--backend",
        default="easyocr",
        choices=available_backends(),
        help="OCR backend (default: easyocr)",
    )
    parser.add_argument(
        "--save-crops", action="store_true", help=f"write cropped plates to {config.OUTPUT_DIR}"
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--quiet", action="store_true", help="suppress progress output")
    parser.add_argument(
        "--fusion",
        default="auto",
        choices=["auto", "probabilistic", "vote"],
        help="how several photos are combined (default: auto, see ADR 0009)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(
        args.images,
        args.model,
        args.conf,
        args.backend,
        args.save_crops,
        args.json,
        args.quiet,
        args.fusion,
    )


__all__ = ["as_dict", "build_parser", "main", "save_crops"]

if __name__ == "__main__":
    raise SystemExit(main())
