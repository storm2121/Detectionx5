"""Validate uploaded photos from their bytes, never from file names or declared types."""

from __future__ import annotations

from io import BytesIO
from typing import Final

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from plate_reader.imaging import Image as Array
from plate_reader.imaging import as_u8

IMAGE_FORMATS: Final = {"JPEG", "PNG", "WEBP", "BMP"}
VIDEO_SUFFIXES: Final = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


def read_photo(upload: UploadFile, max_bytes: int) -> Array:
    """Decoded BGR pixels, or the HTTP error the legacy API also uses (400, 413, 415)."""
    data = upload.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"Each photo must be at most {max_bytes} bytes.")
    if not data:
        raise HTTPException(400, "Photos must not be empty.")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in IMAGE_FORMATS:
                raise HTTPException(415, "Supported photo formats: JPEG, PNG, WebP, BMP.")
            image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(400, "A photo is corrupt or is not a decodable image.") from exc
    decoded = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if decoded is None:
        raise HTTPException(400, "A photo is corrupt or is not a decodable image.")
    return as_u8(decoded)


__all__ = ["IMAGE_FORMATS", "VIDEO_SUFFIXES", "read_photo"]
