"""
OpenTelemetry tracing setup for Driver Service.

Initialises a TracerProvider that exports spans via OTLP gRPC to Jaeger
(or any OTLP-compatible backend).  The endpoint is read from the
OTEL_EXPORTER_OTLP_ENDPOINT environment variable (default: localhost:4317).

Auto-instruments:
  - FastAPI (incoming HTTP requests)
  - SQLAlchemy (database queries)
  - HTTPX (outgoing HTTP calls to client-gateway, etc.)

Usage in main.py:
    from src.telemetry.tracing import init_tracing, instrument_app
    shutdown = init_tracing()       # call once at startup
    instrument_app(app, engine)     # after app + engine are created
    # at shutdown:
    shutdown()
"""

import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

logger = logging.getLogger(__name__)

_tracer_provider: TracerProvider | None = None


def init_tracing() -> callable:
    """
    Bootstrap the OpenTelemetry tracing pipeline.

    Returns a shutdown callable that flushes pending spans.
    """
    global _tracer_provider

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    service_name = os.getenv("OTEL_SERVICE_NAME", "driver-service")

    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: service_name,
        ResourceAttributes.SERVICE_VERSION: "1.0.0",
    })

    _tracer_provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    _tracer_provider.add_span_processor(BatchSpanProcessor(exporter))

    # Register globally so any `trace.get_tracer()` call picks this up
    trace.set_tracer_provider(_tracer_provider)

    logger.info("OpenTelemetry tracing initialised (endpoint=%s, service=%s)", endpoint, service_name)

    def shutdown():
        if _tracer_provider:
            _tracer_provider.shutdown()
            logger.info("OpenTelemetry tracing shut down")

    return shutdown


def instrument_app(app, engine=None):
    """
    Attach auto-instrumentation to FastAPI, SQLAlchemy, and HTTPX.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance.
    engine : sqlalchemy.engine.Engine | None
        The sync engine (used by SQLAlchemy instrumentor).  If the project uses
        only async (asyncpg), pass the sync *engine* from the async engine:
            instrument_app(app, async_engine.sync_engine)
    """
    FastAPIInstrumentor.instrument_app(app)
    logger.info("FastAPI auto-instrumentation enabled")

    if engine is not None:
        SQLAlchemyInstrumentor().instrument(engine=engine)
        logger.info("SQLAlchemy auto-instrumentation enabled")

    HTTPXClientInstrumentor().instrument()
    logger.info("HTTPX auto-instrumentation enabled")
