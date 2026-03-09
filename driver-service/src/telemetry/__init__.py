# Package telemetry — OpenTelemetry tracing and Prometheus metrics for Driver Service.
#
# This module initialises two observability pipelines:
#   1. TRACES  → spans are exported via OTLP gRPC to Jaeger
#   2. METRICS → prometheus-fastapi-instrumentator exposes /metrics for Prometheus
#
# Call init_telemetry() once at application startup (in lifespan).
# Call instrument_app(app) after creating the FastAPI instance.
