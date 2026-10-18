"""Persistence of reads, the review queue and exports; conversion to response bodies.

Crops are written under ``storage/crops/<read id>/<view>.png`` so that a reviewer can see
exactly what the model saw, and so that corrections can be exported as labelled training
crops in the ``data/ocr`` layout (``crop_path,plate_text,format``), which closes the
active-learning loop: export, validate with ``plate data validate``, fine-tune.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from plate_reader.grammar import GRAMMAR, Plate
from plate_reader.normalize import parse_plate

from .db import Database
from .engine import EngineResult
from .models import Export, Read, ReadView, ReviewItem
from .schemas import (
    Candidate,
    Fields,
    PositionOut,
    ReadOut,
    ReadSummary,
    ReviewItemOut,
    ReviewState,
    ViewOut,
    display,
)

EXPORT_COLUMNS = ("crop_path", "plate_text", "format")


def _candidates(pairs: list[Any]) -> list[Candidate]:
    out = []
    for tokens, probability in pairs:
        out.append(
            Candidate(
                plate=display(tokens) or tokens, tokens=tokens, probability=float(probability)
            )
        )
    return out


class Store:
    def __init__(self, db: Database, storage_dir: Path, export_dir: Path, alpha: float) -> None:
        self.db = db
        self.storage_dir = storage_dir
        self.export_dir = export_dir
        self.alpha = alpha

    # --- writing ---------------------------------------------------------------
    def save_read(
        self, result: EngineResult, source: str = "api", job_id: str | None = None
    ) -> str:
        fused = result.fused
        with self.db.session() as session:
            read = Read(
                source=source,
                job_id=job_id,
                status="queued" if result.review_reason else "accepted",
                plate=fused.prediction,
                text=result.plate.text if result.plate else None,
                confidence=float(fused.confidence),
                calibrated=all(v.read.calibrated for v in result.views if v.read is not None)
                and any(v.read is not None for v in result.views),
                prediction_set=list(fused.prediction_set)
                if fused.prediction_set is not None
                else [],
                alpha=self.alpha if fused.prediction_set is not None else None,
                fusion=fused.method,
                model_version=result.model_version,
                posterior=[[t, round(p, 10)] for t, p in fused.posterior[:10]],
                positions=[
                    {
                        "index": p.index,
                        "symbol": p.symbol,
                        "confidence": round(p.confidence, 10),
                        "distribution": [[s, round(q, 10)] for s, q in p.distribution],
                    }
                    for p in fused.positions
                ],
                latency_ms=round(result.latency_ms, 3),
            )
            session.add(read)
            session.flush()
            crop_dir = self.storage_dir / "crops" / read.id
            for view in result.views:
                crop_path: str | None = None
                if view.detection is not None:
                    crop_dir.mkdir(parents=True, exist_ok=True)
                    target = crop_dir / f"{view.index}.png"
                    cv2.imwrite(str(target), view.detection.crop)
                    crop_path = target.as_posix()
                r = view.read
                session.add(
                    ReadView(
                        read_id=read.id,
                        index=view.index,
                        crop_path=crop_path,
                        box=list(view.detection.box) if view.detection is not None else [],
                        detector_confidence=view.detection.confidence if view.detection else 0.0,
                        weight=view.weight,
                        prediction=r.prediction if r else None,
                        confidence=r.confidence if r else None,
                        hypotheses=[[h.tokens, round(h.probability, 10)] for h in r.hypotheses][:10]
                        if r
                        else [],
                        prediction_set=list(r.prediction_set)
                        if r and r.prediction_set is not None
                        else [],
                    )
                )
            if result.review_reason:
                session.add(ReviewItem(read_id=read.id, reason=result.review_reason))
            return read.id

    # --- reading ---------------------------------------------------------------
    def _load(self, session: Session, read_id: str) -> Read | None:
        statement = (
            select(Read)
            .where(Read.id == read_id)
            .options(selectinload(Read.views), selectinload(Read.review))
        )
        return session.scalars(statement).first()

    def read_out(self, read_id: str) -> ReadOut | None:
        with self.db.session() as session:
            read = self._load(session, read_id)
            return to_read_out(read) if read is not None else None

    def list_reads(
        self, status: str | None, limit: int, offset: int
    ) -> tuple[list[ReadSummary], int]:
        with self.db.session() as session:
            query = select(Read).options(selectinload(Read.views))
            count = select(func.count()).select_from(Read)
            if status:
                query = query.where(Read.status == status)
                count = count.where(Read.status == status)
            rows = session.scalars(
                query.order_by(Read.created_at.desc()).limit(limit).offset(offset)
            ).all()
            total = int(session.scalar(count) or 0)
            items = [
                ReadSummary(
                    id=r.id,
                    created_at=r.created_at,
                    plate=r.text,
                    confidence=r.confidence,
                    status=r.status,
                    source=r.source,
                    views=len(r.views),
                )
                for r in rows
            ]
            return items, total

    def crop_path(self, read_id: str, index: int) -> Path | None:
        with self.db.session() as session:
            view = session.scalars(
                select(ReadView).where(ReadView.read_id == read_id, ReadView.index == index)
            ).first()
            if view is None or view.crop_path is None:
                return None
            return Path(view.crop_path)

    # --- review ----------------------------------------------------------------
    def pending_count(self) -> int:
        with self.db.session() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(ReviewItem)
                    .where(ReviewItem.status == "pending")
                )
                or 0
            )

    def review_queue(self, limit: int) -> list[ReviewItemOut]:
        with self.db.session() as session:
            items = session.scalars(
                select(ReviewItem)
                .where(ReviewItem.status == "pending")
                .options(selectinload(ReviewItem.read).selectinload(Read.views))
                .order_by(ReviewItem.created_at)
                .limit(limit)
            ).all()
            return [to_review_out(item) for item in items]

    def decide(self, item_id: str, plate_text: str | None, confirm: bool) -> ReviewItemOut | None:
        with self.db.session() as session:
            item = session.scalars(
                select(ReviewItem)
                .where(ReviewItem.id == item_id)
                .options(selectinload(ReviewItem.read).selectinload(Read.views))
            ).first()
            if item is None:
                return None
            if plate_text is not None:
                item.status = "corrected"
                item.corrected_plate = plate_text
            elif confirm:
                if item.read.text is None:
                    raise ValueError("an unreadable read cannot be confirmed; send the plate")
                item.status = "confirmed"
                item.corrected_plate = item.read.text
            else:
                raise ValueError("send a corrected plate or confirm: true")
            item.reviewed_at = datetime.now(UTC)
            item.read.status = "reviewed"
            session.flush()
            return to_review_out(item)

    def export(self) -> tuple[str, int, list[str], Path]:
        """Write every reviewed, not yet exported read's crops as labelled training crops."""
        crops_dir = self.export_dir / "crops"
        crops_dir.mkdir(parents=True, exist_ok=True)
        labels = self.export_dir / "labels.csv"
        new_file = not labels.exists()
        written: list[str] = []
        with self.db.session() as session:
            items = session.scalars(
                select(ReviewItem)
                .where(
                    ReviewItem.status.in_(("corrected", "confirmed")),
                    ReviewItem.exported_at.is_(None),
                )
                .options(selectinload(ReviewItem.read).selectinload(Read.views))
                .order_by(ReviewItem.reviewed_at)
            ).all()
            rows: list[tuple[str, str, str]] = []
            for item in items:
                plate = parse_plate(item.corrected_plate or "")
                if plate is None:
                    continue
                for view in item.read.views:
                    if view.crop_path is None or not Path(view.crop_path).exists():
                        continue
                    name = f"crops/review_{item.id}_{view.index}.png"
                    (self.export_dir / name).write_bytes(Path(view.crop_path).read_bytes())
                    rows.append((name, plate.text, plate.format))
                    written.append(name)
                item.exported_at = datetime.now(UTC)
            with labels.open("a", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                if new_file:
                    writer.writerow(EXPORT_COLUMNS)
                writer.writerows(rows)
            export = Export(path=self.export_dir.as_posix(), count=len(rows))
            session.add(export)
            session.flush()
            return export.id, len(rows), written, labels


def to_read_out(read: Read) -> ReadOut:
    plate = Plate.from_tokens(read.plate) if read.plate else None
    review = read.review
    return ReadOut(
        id=read.id,
        created_at=read.created_at,
        plate=read.text,
        tokens=read.plate,
        format=GRAMMAR.format_of(read.plate) if read.plate else None,
        fields=Fields.of(plate),
        confidence=read.confidence,
        calibrated=read.calibrated,
        prediction_set=[display(t) or t for t in read.prediction_set]
        if read.alpha is not None
        else None,
        level=round(1.0 - read.alpha, 6) if read.alpha is not None else None,
        fusion=read.fusion,
        model_version=read.model_version,
        review=ReviewState(
            queued=review is not None and review.status == "pending",
            reason=review.reason if review else None,
            item_id=review.id if review else None,
        ),
        views=[
            ViewOut(
                index=v.index,
                box=[int(x) for x in v.box] if v.box else None,
                detector_confidence=v.detector_confidence if v.box else None,
                weight=v.weight,
                prediction=display(v.prediction),
                confidence=v.confidence,
                hypotheses=_candidates(v.hypotheses),
                prediction_set=[display(t) or t for t in v.prediction_set]
                if v.prediction_set
                else None,
            )
            for v in read.views
        ],
        posterior=_candidates(read.posterior),
        positions=[
            PositionOut(
                index=p["index"],
                symbol=p["symbol"],
                confidence=p["confidence"],
                distribution=[{"symbol": s, "probability": q} for s, q in p["distribution"]],
            )
            for p in read.positions
        ],
        latency_ms=read.latency_ms,
        status=read.status,
        source=read.source,
    )


def to_review_out(item: ReviewItem) -> ReviewItemOut:
    read = item.read
    return ReviewItemOut(
        id=item.id,
        read_id=read.id,
        created_at=item.created_at,
        reason=item.reason,
        status=item.status,
        plate=read.text,
        confidence=read.confidence,
        prediction_set=[display(t) or t for t in read.prediction_set]
        if read.alpha is not None
        else None,
        corrected_plate=item.corrected_plate,
        crops=[f"/reads/{read.id}/views/{v.index}/crop" for v in read.views if v.crop_path],
    )


__all__ = ["EXPORT_COLUMNS", "Store", "to_read_out", "to_review_out"]
