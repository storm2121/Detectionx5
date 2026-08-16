#!/usr/bin/env python
"""Command-line entry point.

    python cli.py samples/car.jpg
    python cli.py photo1.jpg photo2.jpg --save-crops
    python cli.py samples/car.jpg --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

import config
from plate_reader import PlateDetector, available_backends, get_backend, read_images


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Detect and read Moroccan licence plates. Runs fully offline.",
    )
    parser.add_argument(
        "images", nargs="+", type=Path, help="one or more image files"
    )
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
        "--save-crops",
        action="store_true",
        help=f"write cropped plates to {config.OUTPUT_DIR}",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="suppress progress output"
    )
    return parser


def save_crops(result, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    # Two inputs can share a stem, so the image's position keeps names unique.
    for position, image_result in enumerate(result.images, start=1):
        for index, reading in enumerate(image_result.readings, start=1):
            name = f"{position:02d}_{image_result.path.stem}_plate{index}.jpg"
            destination = output_dir / name
            cv2.imwrite(str(destination), reading.detection.crop)
            written.append(destination)
    return written


def as_dict(result) -> dict:
    return {
        "plate": result.text,
        "found": result.plate is not None,
        "images_agreeing": result.agreement,
        "images": [
            {
                "path": str(image.path),
                "plates": [
                    {
                        "text": reading.text,
                        "detector_confidence": round(reading.detection.confidence, 4),
                        "box": list(reading.detection.box),
                        "score": round(reading.score, 4),
                        "method": "fields" if reading.segmented else "whole_plate",
                        "fields": reading.components or None,
                    }
                    for reading in image.readings
                ],
            }
            for image in result.images
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    missing = [str(p) for p in args.images if not p.exists()]
    if missing:
        print(f"error: file not found: {', '.join(missing)}", file=sys.stderr)
        return 2

    # JSON output must stay parseable, so progress goes to stderr or nowhere.
    if args.quiet or args.json:
        progress = None
    else:
        progress = print

    try:
        detector = PlateDetector(model_path=args.model, confidence=args.conf)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = read_images(
        args.images,
        detector=detector,
        backend=get_backend(args.backend),
        progress=progress,
    )

    if args.save_crops:
        for path in save_crops(result, config.OUTPUT_DIR):
            if progress:
                progress(f"saved {path}")

    if args.json:
        print(json.dumps(as_dict(result), ensure_ascii=False, indent=2))
    else:
        print()
        if result.plate:
            print(f"Plate: {result.text}")
            if len(result.images) > 1:
                print(f"Agreement: {result.agreement}/{len(result.images)} images")
        else:
            print("Plate: unreadable")

    return 0 if result.plate else 1


if __name__ == "__main__":
    raise SystemExit(main())
