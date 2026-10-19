"""Request and response bodies of the service (Pydantic v2).

Plates are returned in their display spelling (``24830-ب-1``, ``72173 WW``); the canonical
token string is included as ``tokens`` for clients that decode or compare.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from plate_reader.grammar import Plate, to_display
from plate_reader.normalize import parse_plate


def display(tokens: str | None) -> str | None:
    if tokens is None:
        return None
    try:
        return to_display(tokens)
    except ValueError:
        return tokens


class Fields(BaseModel):
    digits: str
    letter: str | None
    region: str | None

    @classmethod
    def of(cls, plate: Plate | None) -> Fields | None:
        if plate is None:
            return None
        return cls(digits=plate.digits, letter=plate.letter, region=plate.region)


class Candidate(BaseModel):
    plate: str
    tokens: str
    probability: float = Field(ge=0.0, le=1.0)


class PositionOut(BaseModel):
    index: int
    symbol: str
    confidence: float
    distribution: list[dict[str, Any]]


class ViewOut(BaseModel):
    index: int
    box: list[int] | None
    detector_confidence: float | None
    weight: float
    prediction: str | None
    confidence: float | None
    hypotheses: list[Candidate]
    prediction_set: list[str] | None


class ReviewState(BaseModel):
    queued: bool
    reason: str | None = None
    item_id: str | None = None


class ReadOut(BaseModel):
    id: str
    created_at: datetime
    plate: str | None
    tokens: str | None
    format: str | None
    fields: Fields | None
    confidence: float = Field(ge=0.0, le=1.0, description="calibrated posterior of the fused read")
    calibrated: bool
    prediction_set: list[str] | None = Field(
        description="conformal set at `level`, display spellings"
    )
    level: float | None
    fusion: str
    model_version: str
    review: ReviewState
    views: list[ViewOut]
    posterior: list[Candidate]
    positions: list[PositionOut]
    latency_ms: float
    status: str
    source: str


class ReadSummary(BaseModel):
    id: str
    created_at: datetime
    plate: str | None
    confidence: float
    status: str
    source: str
    views: int


class ReadPage(BaseModel):
    items: list[ReadSummary]
    total: int
    limit: int
    offset: int


class ReviewItemOut(BaseModel):
    id: str
    read_id: str
    created_at: datetime
    reason: str
    status: str
    plate: str | None
    confidence: float
    prediction_set: list[str] | None
    corrected_plate: str | None
    crops: list[str]


class ReviewDecision(BaseModel):
    """Either a corrected plate (any spelling the grammar parses) or a confirmation."""

    plate: str | None = None
    confirm: bool = False

    @field_validator("plate")
    @classmethod
    def _valid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = parse_plate(value)
        if parsed is None:
            raise ValueError(f"{value!r} is not a valid plate under the grammar")
        return parsed.text


class ExportOut(BaseModel):
    id: str
    exported: int
    path: str
    files: list[str]


class ReviewSummary(BaseModel):
    """What the console's navigation and export button count."""

    pending: int = Field(description="reads waiting for a person")
    ready_to_export: int = Field(description="reviewed reads not exported yet")


class JobRequest(BaseModel):
    kind: Literal["folder", "video"]
    path: str = Field(description="relative to PLATE_JOBS_ROOT")


class JobOut(BaseModel):
    id: str
    kind: str
    source: str
    status: str
    progress: float
    message: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    result: dict[str, Any]
    error: str | None


__all__ = [
    "Candidate",
    "ExportOut",
    "Fields",
    "JobOut",
    "JobRequest",
    "PositionOut",
    "ReadOut",
    "ReadPage",
    "ReadSummary",
    "ReviewDecision",
    "ReviewItemOut",
    "ReviewState",
    "ReviewSummary",
    "ViewOut",
    "display",
]
