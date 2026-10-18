"""HTTP interface for reading several photographs of one vehicle.

Run with ``uvicorn api:app`` from the project root.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from plate_reader import EasyOCRBackend, PlateDetector, read_images

MAX_PHOTOS = 10
MAX_PHOTO_BYTES = 10 * 1024 * 1024
IMAGE_SUFFIXES = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "BMP": ".bmp"}


class PlateFields(BaseModel):
    digits: str
    letter: str | None
    region: str | None


class PlateResponse(BaseModel):
    plate: str | None
    fields: PlateFields | None
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Winning plate's share of weighted votes; not a probability of correctness.",
    )
    images_agreeing: int = Field(ge=0)
    images_processed: int = Field(ge=1)


def _save_photo(upload: UploadFile, destination: Path) -> Path:
    """Validate actual image bytes and choose a suffix without trusting filenames."""
    data = upload.file.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(413, "Each photo must be at most 10 MiB.")
    if not data:
        raise HTTPException(400, "Photos must not be empty.")

    try:
        with Image.open(BytesIO(data)) as image:
            suffix = IMAGE_SUFFIXES.get(image.format)
            if suffix is None:
                raise HTTPException(415, "Supported photo formats: JPEG, PNG, WebP, BMP.")
            image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(400, "A photo is corrupt or is not a decodable image.") from exc

    path = destination.with_suffix(suffix)
    path.write_bytes(data)
    return path


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load everything before serving requests, including the whole-plate fallback.
    app.state.detector = PlateDetector()
    app.state.backend = EasyOCRBackend()
    try:
        app.state.backend.load_models()
        app.state.inference_lock = Lock()
        yield
    finally:
        del app.state.detector
        del app.state.backend


def create_app() -> FastAPI:
    app = FastAPI(title="Moroccan Licence-Plate Reader", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        """Startup completes only after both detection and OCR models are ready."""
        return {"status": "ok"}

    @app.post("/read", response_model=PlateResponse)
    def read_plates(
        request: Request,
        files: Annotated[list[UploadFile], File(description="Photos of the same car.")],
    ) -> PlateResponse:
        """Read one plate by combining votes across one to ten photos."""
        if not files:
            raise HTTPException(422, "Upload at least one photo using the files field.")
        if len(files) > MAX_PHOTOS:
            raise HTTPException(413, "Upload at most 10 photos per request.")

        with TemporaryDirectory(prefix="plate-reader-") as directory:
            paths = [
                _save_photo(upload, Path(directory) / str(index))
                for index, upload in enumerate(files)
            ]
            # These shared inference engines are mutable. Sync routes run in the
            # thread pool, so serializing inference leaves health checks responsive.
            with request.app.state.inference_lock:
                result = read_images(
                    paths,
                    detector=request.app.state.detector,
                    backend=request.app.state.backend,
                )

        total_votes = sum(result.votes.values())
        confidence = (
            result.votes.get(result.plate.text, 0.0) / total_votes
            if result.plate is not None and total_votes > 0
            else 0.0
        )
        return PlateResponse(
            plate=result.plate.text if result.plate else None,
            fields=PlateFields(
                digits=result.plate.digits,
                letter=result.plate.letter,
                region=result.plate.region,
            )
            if result.plate
            else None,
            confidence=confidence,
            images_agreeing=result.agreement,
            images_processed=len(result.images),
        )

    return app


app = create_app()
