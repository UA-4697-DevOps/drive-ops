// ==============================================================================
// K6 LOAD TEST – Trip Service Performance Baseline
// ==============================================================================
// Simulates realistic traffic patterns against Trip Service endpoints.
//
// Usage (local):
//   k6 run load-test.js
//
// Usage (with custom base URL):
//   k6 run -e BASE_URL=http://trip-service.dev.svc.cluster.local load-test.js
//
// Usage (in-cluster via Kubernetes Job):
//   kubectl apply -k .
// ==============================================================================

import http from "k6/http";
import { check, group, sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

// ---------------------------------------------------------------------------
// Custom Metrics
// ---------------------------------------------------------------------------
const tripCreatedCounter = new Counter("trips_created");
const tripFetchedCounter = new Counter("trips_fetched");
const errorRate = new Rate("error_rate");
const tripCreateDuration = new Trend("trip_create_duration", true);
const tripGetDuration = new Trend("trip_get_duration", true);

// ---------------------------------------------------------------------------
// Test Configuration
// ---------------------------------------------------------------------------
const BASE_URL = __ENV.BASE_URL || "http://localhost:8081";

export const options = {
    // Ramp-up → sustained load → ramp-down pattern
    stages: [
        { duration: "2m", target: 50 }, // Warm-up: ramp to 50 VUs
        { duration: "3m", target: 100 }, // Peak:    sustain 100 VUs
        { duration: "2m", target: 50 }, // Cool-down: drop to 50 VUs
        { duration: "1m", target: 0 }, // Drain:   ramp to 0
    ],

    // Performance thresholds (test fails if breached)
    thresholds: {
        http_req_duration: [
            "p(50)<100", // 50th percentile < 100ms
            "p(95)<500", // 95th percentile < 500ms
            "p(99)<1000", // 99th percentile < 1s
        ],
        error_rate: ["rate<0.01"], // Error rate < 1%
        http_req_failed: ["rate<0.01"],
    },

    // Tags for filtering in Grafana / Prometheus
    tags: {
        testName: "trip-service-baseline",
        service: "trip-service",
    },
};

// ---------------------------------------------------------------------------
// Test Scenarios
// ---------------------------------------------------------------------------
export default function () {
    // ----- Health Check (lightweight, high frequency) -----
    group("Health Check", function () {
        const res = http.get(`${BASE_URL}/health`, {
            tags: { endpoint: "health" },
        });

        check(res, {
            "health: status 200": (r) => r.status === 200,
        });

        errorRate.add(res.status !== 200);
    });

    sleep(0.5);

    // ----- Create Trip -----
    let tripId = null;
    group("Create Trip", function () {
        const payload = JSON.stringify({
            rider_id: `rider-${__VU}-${__ITER}`,
            pickup_location: {
                latitude: 40.7128 + Math.random() * 0.01,
                longitude: -74.006 + Math.random() * 0.01,
                address: "123 Test Street, New York, NY",
            },
            dropoff_location: {
                latitude: 40.7589 + Math.random() * 0.01,
                longitude: -73.9851 + Math.random() * 0.01,
                address: "456 Load Test Ave, New York, NY",
            },
        });

        const params = {
            headers: { "Content-Type": "application/json" },
            tags: { endpoint: "create_trip" },
        };

        const res = http.post(`${BASE_URL}/trips`, payload, params);

        const success = check(res, {
            "create trip: status 201": (r) => r.status === 201,
            "create trip: has id": (r) => {
                try {
                    const body = JSON.parse(r.body);
                    return body.id !== undefined && body.id !== "";
                } catch {
                    return false;
                }
            },
        });

        if (success) {
            try {
                const body = JSON.parse(res.body);
                tripId = body.id;
            } catch {
                // ignore parse errors
            }
            tripCreatedCounter.add(1);
        }

        tripCreateDuration.add(res.timings.duration);
        errorRate.add(res.status !== 201);
    });

    sleep(1);

    // ----- Get Trip (if created successfully) -----
    if (tripId) {
        group("Get Trip", function () {
            const res = http.get(`${BASE_URL}/trips/${tripId}`, {
                tags: { endpoint: "get_trip" },
            });

            const success = check(res, {
                "get trip: status 200": (r) => r.status === 200,
                "get trip: correct id": (r) => {
                    try {
                        const body = JSON.parse(r.body);
                        return body.id === tripId;
                    } catch {
                        return false;
                    }
                },
            });

            if (success) {
                tripFetchedCounter.add(1);
            }
            
            tripGetDuration.add(res.timings.duration);
            errorRate.add(res.status !== 200);
        });
    }

    sleep(1);
}

// ---------------------------------------------------------------------------
// Summary Reporter
// ---------------------------------------------------------------------------
export function handleSummary(data) {
    const summary = {
        timestamp: new Date().toISOString(),
        test: "trip-service-baseline",
        metrics: {
            http_req_duration_p50: data.metrics.http_req_duration?.values?.["p(50)"],
            http_req_duration_p95: data.metrics.http_req_duration?.values?.["p(95)"],
            http_req_duration_p99: data.metrics.http_req_duration?.values?.["p(99)"],
            http_req_duration_avg: data.metrics.http_req_duration?.values?.avg,
            http_reqs_total: data.metrics.http_reqs?.values?.count,
            http_reqs_rate: data.metrics.http_reqs?.values?.rate,
            error_rate: data.metrics.error_rate?.values?.rate,
            trips_created: data.metrics.trips_created?.values?.count,
            trips_fetched: data.metrics.trips_fetched?.values?.count,
        },
    };

    return {
        stdout: JSON.stringify(summary, null, 2) + "\n",
        "/tmp/k6-results.json": JSON.stringify(summary, null, 2),
    };
}
