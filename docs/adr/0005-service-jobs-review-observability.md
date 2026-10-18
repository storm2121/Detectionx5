# ADR 0005: FastAPI with Redis-backed jobs, a PostgreSQL review queue and OpenTelemetry

Status: accepted (architect, 2026-10-18). Expand during M4.

## Context

The existing API reads up to ten photos synchronously. Batches and video need background work;
corrections need storage and an export path; operators need latency and confidence metrics.

## Decision

Keep the synchronous `POST /read`; add RQ workers on Redis for folders and video with IoU tracking
and SSE progress; store reads and review decisions in PostgreSQL through SQLAlchemy and Alembic with
a SQLite fallback for tests; export corrections to the data folder; instrument stages with
OpenTelemetry and expose Prometheus metrics with a Grafana dashboard in Compose.

## Consequences

More services in Compose and more operational surface, in exchange for an honest production shape and
a closed active-learning loop. Tests use fake models and SQLite so CI stays fast.
