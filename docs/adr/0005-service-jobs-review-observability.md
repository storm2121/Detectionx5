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

## Consequences

More services in Compose and more operational surface, in exchange for an honest
production shape and a closed active-learning loop. Tests use fake models, SQLite and an
in-process Redis double so CI stays fast.
