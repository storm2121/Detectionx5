"""``plate read``: the original command-line reader, shared with the ``cli.py`` shim."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from ..settings import get_settings

HELP = "Detect and read plates in one or more photos of one car."


def save_crops(result: Any, output_dir: Path) -> list[Path]:
    import cv2

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


def as_dict(result: Any) -> dict[str, Any]:
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


def run(
    images: list[Path],
    model: Path,
    conf: float,
    backend_name: str,
    write_crops: bool,
    as_json: bool,
    quiet: bool,
) -> int:
    """Exit status 0 when a plate was read, 1 when none could be, 2 on bad input."""
    from ..detector import PlateDetector
    from ..ocr import get_backend
    from ..pipeline import read_images

    missing = [str(p) for p in images if not p.exists()]
    if missing:
        print(f"error: file not found: {', '.join(missing)}", file=sys.stderr)
        return 2

    # JSON output must stay parseable, so progress goes nowhere in that mode.
    progress = None if (quiet or as_json) else print

    try:
        detector = PlateDetector(model_path=model, confidence=conf)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = read_images(
        images, detector=detector, backend=get_backend(backend_name), progress=progress
    )

    if write_crops:
        for path in save_crops(result, get_settings().output_dir):
            if progress:
                progress(f"saved {path}")

    if as_json:
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


def command(
    images: Annotated[list[Path], typer.Argument(help="one or more image files")],
    model: Annotated[Path | None, typer.Option(help="YOLO weights (default PLATE_MODEL)")] = None,
    conf: Annotated[float | None, typer.Option(help="detection confidence threshold")] = None,
    backend: Annotated[str, typer.Option(help="OCR backend")] = "easyocr",
    save_crops_: Annotated[
        bool, typer.Option("--save-crops", help="write cropped plates to PLATE_OUTPUT_DIR")
    ] = False,
    json_: Annotated[bool, typer.Option("--json", help="emit machine-readable JSON")] = False,
    quiet: Annotated[bool, typer.Option(help="suppress progress output")] = False,
) -> None:
    settings = get_settings()
    code = run(
        images,
        model or settings.model,
        settings.conf if conf is None else conf,
        backend,
        save_crops_,
        json_,
        quiet,
    )
    raise typer.Exit(code)


__all__ = ["HELP", "as_dict", "command", "run", "save_crops"]
