"""OpenTelemetry tracing setup for client-gateway."""
import logging
import os

logger = logging.getLogger(__name__)


def init_tracing():
    """
    Initialise the OTel TracerProvider and configure OTLP gRPC export to Jaeger.

    Reads from environment:
      OTEL_EXPORTER_OTLP_ENDPOINT — gRPC endpoint (default: Jaeger in-cluster)
      OTEL_SERVICE_NAME            — service name label on spans (default: client-gateway)

    Returns:
        Callable that flushes and shuts down the provider on exit.
    """
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://jaeger.monitoring.svc.cluster.local:4317",
    )
    service_name = os.getenv("OTEL_SERVICE_NAME", "client-gateway")

    provider = TracerProvider()
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    logger.info(
        "OTel tracing initialised → %s (service=%s)", endpoint, service_name,
        extra={"correlationId": "STARTUP"},
    )

    def shutdown():
        provider.shutdown()
        logger.info("OTel tracing shut down", extra={"correlationId": "SHUTDOWN"})

    return shutdown


def instrument_app(app):
    """
    Attach OTel auto-instrumentation to the FastAPI app and all httpx clients.

    Args:
        app: The FastAPI application instance.
    """
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()

    logger.info(
        "OTel instrumentation applied: FastAPI + httpx",
        extra={"correlationId": "STARTUP"},
    )
