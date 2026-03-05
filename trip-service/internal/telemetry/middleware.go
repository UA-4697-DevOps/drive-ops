// Package telemetry — HTTP middleware for tracing and metrics.
//
// This middleware wraps every incoming HTTP request to:
//   1. Create a trace SPAN (so the request appears in Jaeger)
//   2. Record a HISTOGRAM of request duration (for latency percentiles in Grafana)
//   3. Increment a COUNTER of total requests (for request rate / error rate in Grafana)
//   4. Track an UP-DOWN COUNTER of active requests (for the in-flight gauge in Grafana)
//
// How middleware works in Chi:
//   Middleware is a function that wraps an http.Handler. When a request comes in,
//   the middleware runs first (start span, start timer), then calls the next handler
//   (your actual endpoint), then runs cleanup (record duration, set status).
//   r.Use(telemetry.Middleware) applies it to ALL routes.
package telemetry

import (
	"fmt"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/metric"
	"go.opentelemetry.io/otel/trace"
)

// Instruments — the OTel metric instruments used by the middleware.
// These are created once (package-level) and reused on every request.
var (
	// tracer creates spans (units of work in a trace)
	tracer trace.Tracer

	// requestDuration is a HISTOGRAM — it records the distribution of values.
	// Prometheus converts this into "buckets" that let you compute percentiles
	// (p50, p95, p99) using the histogram_quantile() function in PromQL.
	requestDuration metric.Float64Histogram

	// requestTotal is a COUNTER — it only goes up (monotonically increasing).
	// To get "requests per second" in Grafana, you use rate(http_server_requests_total[1m])
	// which calculates the per-second increase over 1 minute.
	requestTotal metric.Int64Counter

	// activeRequests is an UP-DOWN COUNTER (acts like a gauge) — it can go up AND down.
	// It tracks how many requests are currently being processed right now.
	activeRequests metric.Int64UpDownCounter
)

func init() {
	// Get a Tracer from the global TracerProvider (set in telemetry.Init())
	tracer = otel.Tracer("trip-service/http")

	// Get a Meter from the global MeterProvider (set in telemetry.Init())
	meter := otel.Meter("trip-service/http")

	var err error

	// Create the histogram instrument
	// Unit: "s" (seconds) — Grafana panels expect this for latency
	requestDuration, err = meter.Float64Histogram(
		"http_server_request_duration_seconds",
		metric.WithDescription("HTTP request duration in seconds"),
		metric.WithUnit("s"),
	)
	if err != nil {
		panic(fmt.Sprintf("failed to create request_duration histogram: %v", err))
	}

	// Create the counter instrument
	requestTotal, err = meter.Int64Counter(
		"http_server_requests_total",
		metric.WithDescription("Total number of HTTP requests"),
	)
	if err != nil {
		panic(fmt.Sprintf("failed to create requests_total counter: %v", err))
	}

	// Create the up-down counter (gauge-like) instrument
	activeRequests, err = meter.Int64UpDownCounter(
		"http_server_active_requests",
		metric.WithDescription("Number of in-flight HTTP requests"),
	)
	if err != nil {
		panic(fmt.Sprintf("failed to create active_requests gauge: %v", err))
	}
}

// responseWriter wraps http.ResponseWriter to capture the status code.
// The standard http.ResponseWriter doesn't expose the status after WriteHeader(),
// so we wrap it to record the status for our metrics labels.
type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

// Middleware returns Chi-compatible middleware that instruments every request.
//
// For each request it:
//   1. Increments activeRequests (+1)
//   2. Starts a trace span named "HTTP {METHOD} {ROUTE}"
//   3. Records the start time
//   4. Calls the next handler (your actual endpoint code runs here)
//   5. Records the duration as a histogram observation
//   6. Increments the total request counter
//   7. Decrements activeRequests (-1)
//   8. Sets the span status (OK or Error) and ends it
func Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		// +1 active request; defer -1 so the gauge is always decremented,
		// even if a downstream handler panics.
		activeRequests.Add(r.Context(), 1)
		defer activeRequests.Add(r.Context(), -1)

		// Wrap the ResponseWriter to capture the status code
		wrapped := &responseWriter{ResponseWriter: w, statusCode: http.StatusOK}

		// Start a trace span.
		// chi.RouteContext gives us the matched route pattern (e.g. "/trips/{id}")
		// rather than the actual URL (e.g. "/trips/abc-123"), which is better for
		// grouping in both Jaeger and Prometheus labels.
		routePattern := r.URL.Path // fallback
		if rctx := chi.RouteContext(r.Context()); rctx != nil {
			if pattern := rctx.RoutePattern(); pattern != "" {
				routePattern = pattern
			}
		}

		spanName := r.Method + " " + routePattern
		ctx, span := tracer.Start(r.Context(), spanName,
			trace.WithAttributes(
				attribute.String("http.method", r.Method),
				attribute.String("http.route", routePattern),
				attribute.String("http.url", r.URL.String()),
			),
		)
		defer span.End()

		// Call the actual handler with the trace-enriched context
		next.ServeHTTP(wrapped, r.WithContext(ctx))

		// Calculate request duration
		duration := time.Since(start).Seconds()

		// Common labels for all metric instruments
		attrs := metric.WithAttributes(
			attribute.String("method", r.Method),
			attribute.String("route", routePattern),
			attribute.String("status", fmt.Sprintf("%d", wrapped.statusCode)),
		)

		// Record the duration in the histogram
		requestDuration.Record(ctx, duration, attrs)

		// Increment the request counter
		requestTotal.Add(ctx, 1, attrs)

		// Set span status based on HTTP status code
		if wrapped.statusCode >= 400 {
			span.SetStatus(codes.Error, http.StatusText(wrapped.statusCode))
		} else {
			span.SetStatus(codes.Ok, "")
		}

		// Add the status code as a span attribute (visible in Jaeger detail view)
		span.SetAttributes(attribute.Int("http.status_code", wrapped.statusCode))
	})
}
