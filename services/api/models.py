"""The service's tables: reads and their views, the review queue, jobs and exports.

JSON columns hold the structured parts (hypotheses, posteriors, per-position posteriors,
job results) so the schema stays small; everything that is filtered or joined on is a
real column. The schema is created by Alembic (``services/api/migrations``), never by
``create_all`` in production.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSON, list[Any]: JSON}


class Read(Base):
    __tablename__ = "reads"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    source: Mapped[str] = mapped_column(String(16), default="api")  # api | job
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="accepted", index=True)
    plate: Mapped[str | None] = mapped_column(String(32), nullable=True)  # canonical tokens
    text: Mapped[str | None] = mapped_column(String(32), nullable=True)  # display spelling
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    calibrated: Mapped[bool] = mapped_column(Boolean, default=False)
    prediction_set: Mapped[list[Any]] = mapped_column(JSON, default=list)
    alpha: Mapped[float | None] = mapped_column(Float, nullable=True)
    fusion: Mapped[str] = mapped_column(String(32), default="probabilistic")
    model_version: Mapped[str] = mapped_column(String(64), default="")
    posterior: Mapped[list[Any]] = mapped_column(JSON, default=list)
    positions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)

    views: Mapped[list[ReadView]] = relationship(
        back_populates="read", cascade="all, delete-orphan", order_by="ReadView.index"
    )
    review: Mapped[ReviewItem | None] = relationship(back_populates="read", uselist=False)


class ReadView(Base):
    __tablename__ = "read_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    read_id: Mapped[str] = mapped_column(ForeignKey("reads.id", ondelete="CASCADE"), index=True)
    index: Mapped[int] = mapped_column(Integer)
    crop_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    box: Mapped[list[Any]] = mapped_column(JSON, default=list)
    detector_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    prediction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    hypotheses: Mapped[list[Any]] = mapped_column(JSON, default=list)
    prediction_set: Mapped[list[Any]] = mapped_column(JSON, default=list)

    read: Mapped[Read] = relationship(back_populates="views")


class ReviewItem(Base):
    __tablename__ = "review_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    read_id: Mapped[str] = mapped_column(ForeignKey("reads.id", ondelete="CASCADE"), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    reason: Mapped[str] = mapped_column(String(32))  # set_size | low_confidence | unreadable
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    corrected_plate: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    read: Mapped[Read] = relationship(back_populates="review")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    kind: Mapped[str] = mapped_column(String(16))  # folder | video
    source: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    path: Mapped[str] = mapped_column(Text)
    count: Mapped[int] = mapped_column(Integer, default=0)


__all__ = ["Base", "Export", "Job", "Read", "ReadView", "ReviewItem", "new_id", "utcnow"]
