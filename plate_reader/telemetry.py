"""Tracing and metrics: an OpenTelemetry span and a Prometheus histogram per pipeline stage.

Spans are no-ops until :func:`configure_tracing` installs a provider, so the library costs
nothing outside the service. With ``PLATE_OTEL_ENDPOINT`` set, spans are exported over
OTLP/HTTP to the collector in Compose, which forwards them to Grafana's stack.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

from opentelemetry import trace
from opentelemetry.trace import Span
from prometheus_client import Counter, Gauge, Histogram

TRACER_NAME: Final = "detectionx5"
_LATENCY_BUCKETS: Final = (
    0.001,
    0.0025,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)
_CONFIDENCE_BUCKETS: Final = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0)

STAGE_SECONDS: Final = Histogram(
    "plate_stage_seconds", "Time spent in one pipeline stage", ["stage"], buckets=_LATENCY_BUCKETS
)
REQUEST_SECONDS: Final = Histogram(
    "plate_request_seconds", "Request latency by route", ["route"], buckets=_LATENCY_BUCKETS
)
READ_CONFIDENCE: Final = Histogram(
    "plate_read_confidence", "Calibrated confidence of fused reads", buckets=_CONFIDENCE_BUCKETS
)
SET_SIZE: Final = Histogram(
    "plate_prediction_set_size", "Size of the conformal prediction set", buckets=(0, 1, 2, 3, 5, 10)
)
READS: Final = Counter("plate_reads_total", "Fused reads by outcome", ["status"])
JOBS: Final = Counter("plate_jobs_total", "Finished jobs by kind and status", ["kind", "status"])
REVIEW_QUEUE: Final = Gauge("plate_review_queue_size", "Review items waiting for a human")

_configured = False


@contextmanager
def stage(name: str) -> Iterator[Span]:
    """Trace one stage and record its duration."""
    tracer = trace.get_tracer(TRACER_NAME)
    start = time.perf_counter()
    with tracer.start_as_current_span(name) as span:
        try:
            yield span
        finally:
            STAGE_SECONDS.labels(name).observe(time.perf_counter() - start)


def configure_tracing(service_name: str, endpoint: str | None) -> bool:
    """Install a tracer provider once; export over OTLP/HTTP when ``endpoint`` is set."""
    global _configured
    if _configured:
        return False
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _configured = True
    return True


__all__ = [
    "JOBS",
    "READS",
    "READ_CONFIDENCE",
    "REQUEST_SECONDS",
    "REVIEW_QUEUE",
    "SET_SIZE",
    "STAGE_SECONDS",
    "configure_tracing",
    "stage",
]
