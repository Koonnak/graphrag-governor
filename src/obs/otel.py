"""OpenTelemetry wiring for traces and metrics.

Design:
- Emit traces for critical spans (HTTP request, retrieval, generation).
- Emit Prometheus-scrapeable metrics via the Collector (rag_requests_total, rag_latency_ms).
- Fail OPEN: if the collector is unreachable, keep the app running with no-op providers.
"""
from __future__ import annotations
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

from src.config import settings

# Resource describing this service
resource = Resource.create({"service.name": settings.SERVICE_NAME})

try:
    # Traces
    _tracer_provider = TracerProvider(resource=resource)
    _tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.OTEL_ENDPOINT))
    )
    trace.set_tracer_provider(_tracer_provider)
    tracer = trace.get_tracer(__name__)

    # Metrics → exported to Prometheus via the Collector
    _metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=settings.OTEL_ENDPOINT)
    )
    _meter_provider = MeterProvider(resource=resource, metric_readers=[_metric_reader])
    metrics.set_meter_provider(_meter_provider)
    meter = metrics.get_meter(__name__)
except Exception:
    # No-op fallback (keeps the app functional even if OTel is misconfigured)
    tracer = trace.get_tracer(__name__)
    meter = metrics.get_meter(__name__)

# Business metrics (names are stable to ease dashboarding)
rag_requests_total = meter.create_counter("rag_requests_total")
rag_latency_ms = meter.create_histogram("rag_latency_ms")

