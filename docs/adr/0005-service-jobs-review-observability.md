# ADR 0005: FastAPI with Redis-backed jobs, a PostgreSQL review queue and OpenTelemetry

Status: accepted (architect, 2026-10-18); expanded during M0 and M4 by the executing agent.

## Context

The existing API reads up to ten photos synchronously. Batches and video need background
work; corrections need storage and an export path; operators need latency and confidence
metrics.

## Decision

- `services/api`: FastAPI. Keep the synchronous `POST /read`; add `POST /jobs` for folders
  and videos, run by RQ workers on Redis with frame sampling, IoU tracking and per-track
  fusion, with progress over Server-Sent Events at `GET /jobs/{id}/events`.
- Reads and review decisions in PostgreSQL through SQLAlchemy 2 and Alembic; SQLite
  through `PLATE_DB_URL` for tests and single-machine use.
- Review policy: a read is queued when its conformal set has more than one string or its
  calibrated confidence is under a threshold. `POST /review/export` writes corrected crops
  and a `labels.csv` in the `data/ocr/train` layout, closing the active-learning loop.
- OpenTelemetry spans per pipeline stage, Prometheus histograms for latency and
  confidence at `GET /metrics`, a Grafana dashboard JSON under `docs/grafana/`.
- The legacy `api.py` keeps its exact contract (`uvicorn api:app`) until the README is
  rewritten.
- Host ports: API 8100, PostgreSQL 5433, Redis 6380, Prometheus 9100, Grafana 3100,
  OpenTelemetry collector 4319 (gRPC) and 4320 (HTTP), dashboard 5174.

## As built (M4)

- `services/api/main.py`: `create_app(settings, engine_factory, queue_factory)`; the engine
  (`engine.py`) is detection (ONNX detector when `models/detector.onnx` exists, else photos
  are crops; `detect=false` forces crop mode), the CRNN with the constrained beam per view,
  probabilistic fusion with unit weights, the conformal set at `PLATE_ALPHA`, and the review
  policy. Unit weights keep a single view's calibrated posterior intact (weights are
  exponents, ADR 0004); quality weighting is an engine option.
- Review policy: queue when the set holds more than one plate, when the calibrated
  confidence is under `PLATE_REVIEW_THRESHOLD`, or when views were read but no plate came
  out; empty sets are queued only with `PLATE_REVIEW_EMPTY_SETS=true`.
- Storage: crops under `storage/crops/<read>/<view>.png`; `POST /review/export` copies the
  crops of corrected or confirmed reads into `PLATE_EXPORT_DIR` (default `data/ocr/train`)
  and appends `crop_path,plate_text,format` rows, so `plate data validate` and
  `plate train crnn` pick them up unchanged.
- Jobs: the API writes a job row and enqueues `jobs.run_job(job_id, settings)` on RQ; the
  worker writes progress to the row; `GET /jobs/{id}/events` streams it as Server-Sent
  Events by polling the row, which works with PostgreSQL and SQLite and survives a worker
  restart. Videos are sampled every `PLATE_FRAME_STRIDE_SECONDS`, detections are linked by
  greedy IoU matching (`tracking.py`), and each track's best crops (at most ten) are fused
  into one read. Folder and video sources must resolve inside `PLATE_JOBS_ROOT`. On Windows
  the worker is an RQ `SimpleWorker` with a timer-based timeout (no `fork`).
- Schema: SQLAlchemy 2 models and an explicit Alembic migration (`0001`), applied at start-up
  on PostgreSQL in Compose and on SQLite in tests.
- Telemetry: a span and a Prometheus histogram per stage (`plate_reader/telemetry.py`),
  request latency by route, calibrated-confidence and set-size histograms, read outcomes,
  review-queue size, job outcomes. The collector's spanmetrics connector turns spans into
  request-rate and duration metrics that Prometheus scrapes; traces themselves are logged by
  the collector (no trace store such as Tempo is in the Compose service list).
- Containers: `Dockerfile.api` and `Dockerfile.worker` install only the runtime
  dependencies (no PyTorch, ADR 0007) with the CRNN and detector ONNX files;
  `Dockerfile.dashboard` serves a placeholder page until M5.
- The detector is exported with Ultralytics' `nms=False`, which keeps YOLOv10's NMS-free
  one-to-one head (`(1, 300, 6)` boxes), the same head the PyTorch path selects; the
  default export emits the one-to-many head, which would need NMS and would not match. The
  export has dynamic height and width so the ONNX detector letterboxes to the same minimum
  stride-aligned rectangle as Ultralytics' PyTorch predictor; padding to a square instead
  changed confidences noticeably (`tests/test_tracking_registry.py` checks the parity).

## Consequences

More services in Compose and more operational surface, in exchange for an honest
production shape and a closed active-learning loop. Tests use fake models, SQLite and an
in-process Redis double so CI stays fast.
