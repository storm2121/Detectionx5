"""Service settings, read from ``PLATE_*`` environment variables like the rest of the project.

Defaults make a single machine work out of the box (SQLite under ``storage/``, models from
``models/``, Redis on the project's host port); Compose overrides them with service names.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from plate_reader.settings import PROJECT_ROOT


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PLATE_", extra="ignore")

    db_url: str = Field(
        default=f"sqlite:///{(PROJECT_ROOT / 'storage' / 'plates.db').as_posix()}",
        description="SQLAlchemy URL; PostgreSQL in Compose, SQLite by default",
    )
    redis_url: str = Field(default="redis://localhost:6380/0", description="RQ queue backend")
    queue_name: str = "plates"
    storage_dir: Path = Field(default=PROJECT_ROOT / "storage", description="crops and uploads")
    jobs_root: Path = Field(
        default=PROJECT_ROOT / "storage" / "jobs", description="folders and videos jobs may read"
    )
    export_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "ocr" / "train", description="where corrections go"
    )
    crnn_model: Path = Field(default=PROJECT_ROOT / "models" / "crnn.onnx")
    detector_model: Path = Field(
        default=PROJECT_ROOT / "models" / "detector.onnx",
        description="ONNX detector; without it photos are read as plate crops",
    )
    registry_path: Path = Field(default=PROJECT_ROOT / "models" / "registry.json")
    results_dir: Path = Field(
        default=PROJECT_ROOT / "results",
        description="committed evaluation results (JSON) that the dashboard renders",
    )
    review_threshold: float = Field(default=0.9, ge=0.0, le=1.0)
    review_skip_empty_sets: bool = Field(
        default=False,
        description="do not queue reads whose conformal set is empty (they are queued by default)",
    )
    alpha: float = Field(
        default=0.05, gt=0.0, lt=1.0, description="conformal miscoverage of the served sets"
    )
    max_photos: int = Field(default=10, ge=1)
    max_photo_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    frame_stride_seconds: float = Field(default=0.5, gt=0.0, description="video sampling")
    otel_endpoint: str | None = Field(default=None, description="OTLP/HTTP collector URL")
    migrate: bool = Field(default=True, description="run Alembic migrations at start-up")

    @field_validator(
        "storage_dir",
        "jobs_root",
        "export_dir",
        "crnn_model",
        "detector_model",
        "registry_path",
        "results_dir",
        mode="after",
    )
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser().resolve()


@lru_cache(maxsize=1)
def get_service_settings() -> ServiceSettings:
    return ServiceSettings()


__all__ = ["ServiceSettings", "get_service_settings"]
