// Package telemetry initialises OpenTelemetry tracing and metrics for Trip Service.
//
// What is OpenTelemetry (OTel)?
//   OpenTelemetry is a vendor-neutral, open-source observability framework
//   (CNCF project) that provides a single set of APIs and SDKs to instrument
//   your code. It replaces the now-deprecated Jaeger and Zipkin client libraries.
//
// This package sets up two "pipelines":
//   1. TRACES  → spans are exported via OTLP gRPC to Jaeger
//   2. METRICS → counters/histograms are exposed at /metrics for Prometheus to scrape
//
// The Init() function must be called once at application startup (in main.go).
// It returns a shutdown function that must be deferred to flush any pending data.
package telemetry

import (
	"context"
	"errors"
	"log"
	"net/http"
	"os"

	// Prometheus exporter — creates a /metrics HTTP handler that Prometheus scrapes
	promexporter "go.opentelemetry.io/otel/exporters/prometheus"

	// OTLP trace exporter — sends spans to Jaeger (or any OTLP-compatible backend) via gRPC
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"

	// OTel core API — global tracer/meter registration
	"go.opentelemetry.io/otel"

	// OTel resource — attaches metadata (service name, version) to all telemetry
	"go.opentelemetry.io/otel/sdk/resource"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"

	// OTel SDK implementations
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"

	// Prometheus client — provides the HTTP handler that serves /metrics
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// metricsHandler is the HTTP handler that serves /metrics in Prometheus format.
// It is set during Init() and returned via MetricsHandler().
var metricsHandler http.Handler

// Init bootstraps the OpenTelemetry tracing and metrics pipelines.
//
// What happens inside:
//   1. Creates a Resource that tags all telemetry with service.name = "trip-service"
//   2. Creates an OTLP gRPC exporter that sends trace spans to Jaeger
//   3. Creates a TracerProvider (the component that generates spans) and registers it globally
//   4. Creates a Prometheus exporter that collects metrics and serves them at /metrics
//   5. Creates a MeterProvider (the component that records metrics) and registers it globally
//
// Returns a shutdown function that should be deferred in main().
func Init(ctx context.Context) (shutdown func(context.Context) error, err error) {
	// --- Step 1: Resource ---
	// A Resource describes the entity producing telemetry.
	// semconv.ServiceNameKey is a standard attribute ("service.name")
	// that Jaeger and Prometheus use to identify the service.
	res, err := resource.Merge(
		resource.Default(),
		resource.NewWithAttributes(
			resource.Default().SchemaURL(),
			semconv.ServiceName("trip-service"),
			semconv.ServiceVersion("1.0.0"),
		),
	)
	if err != nil {
		return nil, err
	}

	// --- Step 2: OTLP Trace Exporter ---
	// This exporter serialises spans into the OTLP protobuf format and sends
	// them over gRPC to the endpoint specified in OTEL_EXPORTER_OTLP_ENDPOINT.
	//
	// Default: "localhost:4317" — in K8s we set this env var to
	// "jaeger.monitoring.svc.cluster.local:4317" so spans reach the Jaeger collector.
	//
	// WithInsecure() disables TLS (fine for in-cluster communication).
	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		endpoint = "localhost:4317"
	}
	traceExporter, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithEndpoint(endpoint),
		otlptracegrpc.WithInsecure(),
	)
	if err != nil {
		return nil, err
	}

	// --- Step 3: TracerProvider ---
	// The TracerProvider is the "factory" for creating Tracers, which in turn
	// create Spans. We configure it with:
	//   - BatchSpanProcessor: batches spans before sending to reduce network overhead
	//   - The Resource we created above (so every span is tagged with service.name)
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(traceExporter),
		sdktrace.WithResource(res),
	)
	// Register globally so any code calling otel.Tracer("name") gets our configured provider
	otel.SetTracerProvider(tp)
	log.Println("INFO: OpenTelemetry TracerProvider initialised (exporting to " + endpoint + ")")

	// --- Step 4: Prometheus Metric Exporter ---
	// Unlike the trace exporter (which pushes), the Prometheus exporter is pull-based:
	// it collects metrics in memory, and Prometheus HTTP-GETs them via /metrics.
	//
	// The promexporter.New() call creates both a metric reader AND registers a
	// default Prometheus registry that promhttp.Handler() will serve.
	promReader, err := promexporter.New()
	if err != nil {
		// Roll back the already-initialised TracerProvider so we don't
		// leak its background goroutines and OTLP connection.
		if shutdownErr := tp.Shutdown(context.Background()); shutdownErr != nil {
			log.Printf("ERROR: TracerProvider rollback shutdown: %v", shutdownErr)
		}
		return nil, err
	}

	// --- Step 5: MeterProvider ---
	// The MeterProvider is the "factory" for creating Meters, which record
	// counters, histograms, and gauges. We use the Prometheus reader so all
	// recorded metrics appear on /metrics.
	mp := sdkmetric.NewMeterProvider(
		sdkmetric.WithReader(promReader),
		sdkmetric.WithResource(res),
	)
	otel.SetMeterProvider(mp)
	log.Println("INFO: OpenTelemetry MeterProvider initialised (Prometheus /metrics)")

	// Set the metrics handler for use by MetricsHandler()
	metricsHandler = promhttp.Handler()

	// Return a combined shutdown function that flushes both providers
	shutdown = func(ctx context.Context) error {
		var errs []error
		if err := tp.Shutdown(ctx); err != nil {
			log.Printf("ERROR: TracerProvider shutdown: %v", err)
			errs = append(errs, err)
		}
		if err := mp.Shutdown(ctx); err != nil {
			log.Printf("ERROR: MeterProvider shutdown: %v", err)
			errs = append(errs, err)
		}
		return errors.Join(errs...)
	}

	return shutdown, nil
}

// MetricsHandler returns the HTTP handler that serves the /metrics endpoint
// in Prometheus exposition format. This handler is created during Init().
//
// Example usage in main.go:
//
//	r.Handle("/metrics", telemetry.MetricsHandler())
func MetricsHandler() http.Handler {
	if metricsHandler == nil {
		// Fallback if Init() wasn't called — return a no-op handler
		return http.NotFoundHandler()
	}
	return metricsHandler
}
