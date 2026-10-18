"""The plate-reading service (ARCHITECTURE §11).

``uvicorn services.api.main:app`` serves synchronous reads of one to ten photos, the read
log, the review queue and its export, background jobs with live progress, the model
registry, health and Prometheus metrics. The inference engine, the database URL and the
job queue are injected through :func:`create_app`, which is how the tests run every
endpoint with fake models, SQLite and an in-process Redis double.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from plate_reader import __version__
from plate_reader.telemetry import (
    READ_CONFIDENCE,
    READS,
    REQUEST_SECONDS,
    REVIEW_QUEUE,
    SET_SIZE,
    configure_tracing,
    stage,
)

from .config import ServiceSettings, get_service_settings
from .db import Database, migrate
from .engine import Engine
from .models import Job
from .schemas import ExportOut, JobOut, JobRequest, ReadOut, ReadPage, ReviewDecision, ReviewItemOut
from .store import Store
from .uploads import VIDEO_SUFFIXES, read_photo

EngineFactory = Callable[[ServiceSettings], Engine]
QueueFactory = Callable[[ServiceSettings], Any]


def build_engine(settings: ServiceSettings) -> Engine:
    """The production engine: ONNX CRNN with the constrained beam, ONNX detector if present."""
    from plate_reader.detector_onnx import OnnxPlateDetector
    from plate_reader.eval.recognizers import CRNNRecognizer

    recognizer = CRNNRecognizer("beam", settings.crnn_model, alpha=settings.alpha)
    detector = (
        OnnxPlateDetector(settings.detector_model) if settings.detector_model.exists() else None
    )
    return Engine(
        recognizer,
        detector,
        review_threshold=settings.review_threshold,
        review_empty_sets=settings.review_empty_sets,
    )


def redis_queue(settings: ServiceSettings) -> Any:
    from redis import Redis
    from rq import Queue

    connection = Redis.from_url(settings.redis_url, socket_connect_timeout=2)
    return Queue(settings.queue_name, connection=connection)


def _job_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        kind=job.kind,
        source=Path(job.source).name,
        status=job.status,
        progress=job.progress,
        message=job.message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        result=job.result,
        error=job.error,
    )


def create_app(
    settings: ServiceSettings | None = None,
    engine_factory: EngineFactory = build_engine,
    queue_factory: QueueFactory = redis_queue,
) -> FastAPI:
    config = settings or get_service_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_tracing("detectionx5-api", config.otel_endpoint)
        if config.migrate:
            migrate(config.db_url)
        app.state.db = Database(config.db_url)
        app.state.store = Store(app.state.db, config.storage_dir, config.export_dir, config.alpha)
        app.state.engine = engine_factory(config)
        app.state.queue = queue_factory(config)
        try:
            yield
        finally:
            app.state.db.dispose()

    app = FastAPI(title="DetectionX5 plate service", version=__version__, lifespan=lifespan)

    @app.middleware("http")
    async def timing(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        name = getattr(route, "path", "unmatched")
        REQUEST_SECONDS.labels(name).observe(time.perf_counter() - start)
        return response

    def store_of(request: Request) -> Store:
        store: Store = request.app.state.store
        return store

    # --- reads ---------------------------------------------------------------------
    @app.post("/read", response_model=ReadOut)
    def read(
        request: Request,
        files: Annotated[list[UploadFile], File(description="One to ten photos of the same car.")],
        detect: Annotated[
            bool, Query(description="run the detector; false reads each photo as a plate crop")
        ] = True,
    ) -> ReadOut:
        """Detect, read and fuse; returns calibrated confidence and the conformal set."""
        if not files:
            raise HTTPException(422, "Upload at least one photo using the files field.")
        if len(files) > config.max_photos:
            raise HTTPException(413, f"Upload at most {config.max_photos} photos per request.")
        images = [read_photo(upload, config.max_photo_bytes) for upload in files]
        engine: Engine = request.app.state.engine
        with stage("read"):
            result = engine.read(images, detect=detect)
        store = store_of(request)
        with stage("store"):
            read_id = store.save_read(result)
        READS.labels("queued" if result.review_reason else "accepted").inc()
        READ_CONFIDENCE.observe(result.fused.confidence)
        if result.fused.prediction_set is not None:
            SET_SIZE.observe(len(result.fused.prediction_set))
        out = store.read_out(read_id)
        assert out is not None
        return out

    @app.get("/reads", response_model=ReadPage)
    def reads(
        request: Request,
        status: Annotated[str | None, Query(pattern="^(accepted|queued|reviewed)$")] = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> ReadPage:
        items, total = store_of(request).list_reads(status, limit, offset)
        return ReadPage(items=items, total=total, limit=limit, offset=offset)

    @app.get("/reads/{read_id}", response_model=ReadOut)
    def read_detail(request: Request, read_id: str) -> ReadOut:
        out = store_of(request).read_out(read_id)
        if out is None:
            raise HTTPException(404, "No such read.")
        return out

    @app.get("/reads/{read_id}/views/{index}/crop")
    def crop(request: Request, read_id: str, index: int) -> FileResponse:
        path = store_of(request).crop_path(read_id, index)
        if path is None or not path.exists():
            raise HTTPException(404, "No crop for that view.")
        return FileResponse(path, media_type="image/png")

    # --- review --------------------------------------------------------------------
    @app.get("/review/queue", response_model=list[ReviewItemOut])
    def review_queue(
        request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 50
    ) -> list[ReviewItemOut]:
        return store_of(request).review_queue(limit)

    @app.post("/review/export", response_model=ExportOut)
    def review_export(request: Request) -> ExportOut:
        """Write reviewed crops and labels into the data/ocr/train layout."""
        export_id, count, files, labels = store_of(request).export()
        return ExportOut(id=export_id, exported=count, path=labels.as_posix(), files=files)

    @app.post("/review/{item_id}", response_model=ReviewItemOut)
    def review_decide(request: Request, item_id: str, decision: ReviewDecision) -> ReviewItemOut:
        try:
            out = store_of(request).decide(item_id, decision.plate, decision.confirm)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if out is None:
            raise HTTPException(404, "No such review item.")
        return out

    # --- jobs ----------------------------------------------------------------------
    def _enqueue(request: Request, kind: str, source: Path) -> JobOut:
        queue = request.app.state.queue
        if queue is None:
            raise HTTPException(503, "The job queue is not configured.")
        db: Database = request.app.state.db
        with db.session() as session:
            job = Job(kind=kind, source=source.as_posix(), message="queued")
            session.add(job)
            session.flush()
            job_id = job.id
        try:
            from .jobs import run_job

            queue.enqueue(run_job, job_id, config.model_dump(mode="json"), job_timeout=3600)
        except Exception as exc:  # Redis down: tell the client instead of hanging the job
            with db.session() as session:
                stored = session.get(Job, job_id)
                if stored is not None:
                    stored.status, stored.error = "failed", f"queue unavailable: {exc}"
            raise HTTPException(503, "The job queue is unavailable.") from exc
        with db.session() as session:
            stored = session.get(Job, job_id)
            assert stored is not None
            return _job_out(stored)

    @app.post("/jobs", response_model=JobOut, status_code=202)
    def create_job(request: Request, body: JobRequest) -> JobOut:
        """Queue a folder of photos or a video that lives under PLATE_JOBS_ROOT."""
        root = config.jobs_root
        source = (root / body.path).resolve()
        if root.resolve() not in (source, *source.parents):
            raise HTTPException(400, "The path must stay inside the jobs root.")
        if body.kind == "folder" and not source.is_dir():
            raise HTTPException(404, "No such folder under the jobs root.")
        if body.kind == "video" and not (
            source.is_file() and source.suffix.lower() in VIDEO_SUFFIXES
        ):
            raise HTTPException(404, "No such video under the jobs root.")
        return _enqueue(request, body.kind, source)

    @app.post("/jobs/upload", response_model=JobOut, status_code=202)
    def upload_job(request: Request, video: Annotated[UploadFile, File()]) -> JobOut:
        suffix = Path(video.filename or "").suffix.lower()
        if suffix not in VIDEO_SUFFIXES:
            raise HTTPException(415, "Supported videos: " + ", ".join(sorted(VIDEO_SUFFIXES)))
        target = config.jobs_root / "uploads" / f"{uuid.uuid4().hex}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as handle:
            while chunk := video.file.read(1024 * 1024):
                handle.write(chunk)
        return _enqueue(request, "video", target)

    @app.get("/jobs/{job_id}", response_model=JobOut)
    def job_detail(request: Request, job_id: str) -> JobOut:
        db: Database = request.app.state.db
        with db.session() as session:
            job = session.get(Job, job_id)
            if job is None:
                raise HTTPException(404, "No such job.")
            return _job_out(job)

    @app.get("/jobs/{job_id}/events")
    async def job_events(request: Request, job_id: str) -> StreamingResponse:
        """Server-Sent Events: ``progress`` on every change, ``done`` at the end."""
        db: Database = request.app.state.db

        def load() -> JobOut | None:
            with db.session() as session:
                job = session.get(Job, job_id)
                return _job_out(job) if job is not None else None

        if await run_in_threadpool(load) is None:
            raise HTTPException(404, "No such job.")

        async def stream() -> AsyncIterator[str]:
            last: dict[str, Any] | None = None
            idle = 0.0
            while True:
                job = await run_in_threadpool(load)
                if job is None:  # pragma: no cover - deleted while streaming
                    return
                state = {
                    "status": job.status,
                    "progress": round(job.progress, 4),
                    "message": job.message,
                }
                if state != last:
                    yield f"event: progress\ndata: {json.dumps(state)}\n\n"
                    last, idle = state, 0.0
                if job.status in ("finished", "failed"):
                    yield f"event: done\ndata: {job.model_dump_json()}\n\n"
                    return
                await asyncio.sleep(0.25)
                idle += 0.25
                if idle >= 15.0:
                    yield ": keep-alive\n\n"
                    idle = 0.0

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    # --- models, health, metrics ---------------------------------------------------------
    @app.get("/models")
    def models(request: Request) -> dict[str, Any]:
        engine: Engine = request.app.state.engine
        runtime = getattr(engine.recognizer, "runtime", None)
        metadata = runtime.metadata.as_dict() if runtime is not None else None
        detector = engine.detector
        registry: dict[str, Any] = {"models": [], "active": {}}
        if config.registry_path.exists():
            registry = json.loads(config.registry_path.read_text(encoding="utf-8"))
        return {
            "recognizer": {
                "name": engine.recognizer.name,
                "version": engine.model_version,
                "metadata": metadata,
            },
            "detector": {
                "available": detector is not None,
                "path": Path(getattr(detector, "model_path", "")).name
                if detector is not None
                else None,
            },
            "fusion": engine.fusion,
            "alpha": config.alpha,
            "review_threshold": config.review_threshold,
            "registry": registry,
        }

    @app.get("/health")
    def health(request: Request) -> dict[str, Any]:
        db: Database = request.app.state.db
        try:
            with db.session() as session:
                session.execute(text("SELECT 1"))
            database = "ok"
        except Exception:  # pragma: no cover - reported, not raised
            database = "unavailable"
        queue = request.app.state.queue
        queue_state = "not configured"
        if queue is not None:
            try:
                queue.connection.ping()
                queue_state = "ok"
            except Exception:
                queue_state = "unavailable"
        engine: Engine = request.app.state.engine
        return {
            "status": "ok" if database == "ok" else "degraded",
            "database": database,
            "queue": queue_state,
            "model_version": engine.model_version,
            "detector": engine.detector is not None,
        }

    @app.get("/metrics")
    def metrics(request: Request) -> Response:
        REVIEW_QUEUE.set(store_of(request).pending_count())
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()

__all__ = ["app", "build_engine", "create_app", "redis_queue"]
