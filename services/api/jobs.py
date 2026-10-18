"""Background jobs: a folder of photos (one read each) or a video (one read per track).

Jobs run in RQ workers. Progress is written to the job's row, which the API streams to
clients as Server-Sent Events, so progress survives worker restarts and works the same
with PostgreSQL and SQLite. A video is sampled every ``frame_stride_seconds``, detections
are linked into tracks by IoU, and each track's best crops are fused into one read.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import cv2

from plate_reader.data.layout import IMAGE_SUFFIXES
from plate_reader.imaging import as_u8
from plate_reader.telemetry import JOBS, stage

from .config import ServiceSettings, get_service_settings
from .db import Database
from .engine import Engine
from .models import Job
from .store import Store
from .tracking import IoUTracker

#: The most views fused for one video track (the API's photo limit).
MAX_TRACK_VIEWS: Final = 10

EngineFactory = Callable[[ServiceSettings], Engine]
_ENGINES: dict[str, Engine] = {}


def default_engine_factory(settings: ServiceSettings) -> Engine:
    from .main import build_engine

    return build_engine(settings)


#: Replaced by tests (the worker builds the real engine once per process).
ENGINE_FACTORY: EngineFactory = default_engine_factory


def _engine(settings: ServiceSettings) -> Engine:
    key = f"{settings.crnn_model}|{settings.detector_model}"
    if key not in _ENGINES:
        _ENGINES[key] = ENGINE_FACTORY(settings)
    return _ENGINES[key]


def _update(db: Database, job_id: str, **fields: Any) -> None:
    with db.session() as session:
        job = session.get(Job, job_id)
        if job is not None:
            for key, value in fields.items():
                setattr(job, key, value)


def _run_folder(
    folder: Path, engine: Engine, store: Store, db: Database, job_id: str
) -> dict[str, Any]:
    images = sorted(p for p in folder.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES)
    reads: list[dict[str, Any]] = []
    for done, path in enumerate(images, start=1):
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            reads.append(
                {"image": path.relative_to(folder).as_posix(), "error": "unreadable image"}
            )
        else:
            result = engine.read([as_u8(image)])
            read_id = store.save_read(result, source="job", job_id=job_id)
            reads.append(
                {
                    "image": path.relative_to(folder).as_posix(),
                    "read_id": read_id,
                    "plate": result.plate.text if result.plate else None,
                    "queued": result.review_reason is not None,
                }
            )
        _update(
            db, job_id, progress=done / max(1, len(images)), message=f"{done}/{len(images)} photos"
        )
    return {"items": len(images), "reads": reads}


def _run_video(
    video: Path, engine: Engine, store: Store, db: Database, job_id: str, stride_seconds: float
) -> dict[str, Any]:
    detector = engine.detector
    if detector is None:
        raise RuntimeError("video jobs need a detector model (models/detector.onnx)")
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video {video.name}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    step = max(1, round(fps * stride_seconds))
    tracker = IoUTracker()
    frame_index = sampled = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index % step == 0:
                with stage("track"):
                    tracker.update(frame_index, detector.detect_image(as_u8(frame)))
                sampled += 1
                _update(
                    db,
                    job_id,
                    progress=0.8 * min(1.0, frame_index / total),
                    message=f"frame {frame_index}/{total}",
                )
            frame_index += 1
    finally:
        capture.release()
    tracks_out = []
    tracks = tracker.finish()
    for number, track in enumerate(tracks, start=1):
        best = sorted(track.observations, key=lambda o: o[1].confidence, reverse=True)[
            :MAX_TRACK_VIEWS
        ]
        result = engine.read_detections([det for _, det in sorted(best, key=lambda o: o[0])])
        read_id = store.save_read(result, source="job", job_id=job_id)
        tracks_out.append(
            {
                "track": track.id,
                "frames": track.frames,
                "read_id": read_id,
                "plate": result.plate.text if result.plate else None,
                "queued": result.review_reason is not None,
            }
        )
        _update(
            db,
            job_id,
            progress=0.8 + 0.2 * number / max(1, len(tracks)),
            message=f"track {number}/{len(tracks)}",
        )
    return {"frames": frame_index, "sampled": sampled, "fps": fps, "tracks": tracks_out}


def run_job(job_id: str, settings_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """The RQ entry point. Failures are recorded on the job row, not re-raised.

    The API passes its own settings, so a worker writes reads and crops exactly where the
    API that queued the job reads them.
    """
    settings = ServiceSettings(**settings_data) if settings_data else get_service_settings()
    db = Database(settings.db_url)
    store = Store(db, settings.storage_dir, settings.export_dir, settings.alpha)
    kind = "unknown"
    try:
        with db.session() as session:
            job = session.get(Job, job_id)
            if job is None:
                return {"error": "no such job"}
            kind, source = job.kind, job.source
            job.status, job.started_at = "running", datetime.now(UTC)
        engine = _engine(settings)
        path = Path(source)
        with stage(f"job_{kind}"):
            if kind == "folder":
                result = _run_folder(path, engine, store, db, job_id)
            else:
                result = _run_video(path, engine, store, db, job_id, settings.frame_stride_seconds)
        _update(
            db,
            job_id,
            status="finished",
            progress=1.0,
            message="done",
            result=result,
            finished_at=datetime.now(UTC),
        )
        JOBS.labels(kind, "finished").inc()
        return result
    except Exception as exc:  # recorded for the client; the worker keeps running
        _update(db, job_id, status="failed", error=str(exc), finished_at=datetime.now(UTC))
        JOBS.labels(kind, "failed").inc()
        return {"error": str(exc)}
    finally:
        db.dispose()


__all__ = ["ENGINE_FACTORY", "MAX_TRACK_VIEWS", "default_engine_factory", "run_job"]
