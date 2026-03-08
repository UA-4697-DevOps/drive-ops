#!/bin/bash
# ---------------------------------------------------------------------------
# web-client-load-test.sh — Load test for web-client HPA validation
#
# Uses 'hey' (HTTP load generator) to generate sustained traffic against the
# web-client, then watches HPA scaling behavior.
#
# Prerequisites:
#   - hey        (go install github.com/rakyll/hey@latest)
#                 or: brew install hey / apt install hey
#   - kubectl    (configured for the target cluster)
#   - Optional: metrics-server running in the cluster
#
# Usage:
#   # Port-forward first (or use Ingress URL):
#   kubectl -n web-client port-forward svc/web-client 8083:80 &
#
#   # Run the load test:
#   ./web-client-load-test.sh [TARGET_URL] [DURATION] [CONCURRENCY]
#
#   # Examples:
#   ./web-client-load-test.sh                           # defaults
#   ./web-client-load-test.sh http://localhost:8083 60s 100
#   ./web-client-load-test.sh https://web.example.com 120s 200
# ---------------------------------------------------------------------------

set -euo pipefail

TARGET_URL="${1:-http://localhost:8083}"
DURATION="${2:-60s}"
CONCURRENCY="${3:-50}"
NAMESPACE="web-client"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
log "Preflight checks..."

if ! command -v hey &>/dev/null; then
    err "'hey' is not installed. Install it with:"
    echo "  go install github.com/rakyll/hey@latest"
    echo "  OR: brew install hey / apt install hey"
    exit 1
fi

# Quick connectivity check
if curl -sf --max-time 5 "${TARGET_URL}/health" > /dev/null 2>&1; then
    ok "web-client reachable at ${TARGET_URL}/health"
else
    err "Cannot reach ${TARGET_URL}/health — is the service running / port-forwarded?"
    exit 1
fi

# ---------------------------------------------------------------------------
# Baseline snapshot
# ---------------------------------------------------------------------------
log "Taking baseline snapshot..."

echo ""
echo "=== Current HPA State ==="
kubectl get hpa -n "$NAMESPACE" 2>/dev/null || warn "No HPA found (is it deployed?)"
echo ""
echo "=== Current Pods ==="
kubectl get pods -n "$NAMESPACE" -o wide 2>/dev/null || warn "Cannot list pods"
echo ""

BASELINE_PODS=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)
log "Baseline pod count: ${BASELINE_PODS}"

# ---------------------------------------------------------------------------
# Phase 1: Static content load test (/ endpoint)
# ---------------------------------------------------------------------------
echo ""
log "Phase 1: Static content — ${DURATION} at ${CONCURRENCY} concurrent connections"
log "Target: ${TARGET_URL}/"
echo "---"

hey -z "$DURATION" -c "$CONCURRENCY" -m GET "${TARGET_URL}/"

# ---------------------------------------------------------------------------
# Phase 2: API proxy load test (/api/drivers)
# ---------------------------------------------------------------------------
echo ""
echo "---"
log "Phase 2: API proxy — ${DURATION} at ${CONCURRENCY} concurrent connections"
log "Target: ${TARGET_URL}/api/drivers"
echo "---"

hey -z "$DURATION" -c "$CONCURRENCY" -m GET "${TARGET_URL}/api/drivers" || warn "API proxy test failed (driver-service may not be running)"

# ---------------------------------------------------------------------------
# Phase 3: Watch HPA react
# ---------------------------------------------------------------------------
echo ""
echo "---"
log "Waiting 30s for HPA to react..."
sleep 30

echo ""
echo "=== HPA State After Load ==="
kubectl get hpa -n "$NAMESPACE" 2>/dev/null || warn "No HPA found"
echo ""
echo "=== Pods After Load ==="
kubectl get pods -n "$NAMESPACE" -o wide 2>/dev/null || warn "Cannot list pods"
echo ""

POST_PODS=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)
log "Post-load pod count: ${POST_PODS} (was: ${BASELINE_PODS})"

if [ "$POST_PODS" -gt "$BASELINE_PODS" ]; then
    ok "HPA scaled up: ${BASELINE_PODS} → ${POST_PODS} pods"
else
    warn "HPA did not scale up (load may have been insufficient, or metrics-server is slow)"
fi

# ---------------------------------------------------------------------------
# Phase 4: Cool-down observation
# ---------------------------------------------------------------------------
echo ""
log "Observing scale-down (stabilizationWindow = 300s). Press Ctrl+C to stop."
log "Run this in parallel to watch live:"
echo "  kubectl get hpa -n ${NAMESPACE} -w"
echo ""

for i in {1..6}; do
    sleep 60
    CURRENT=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)
    log "T+${i}min — pods: ${CURRENT}"
    kubectl get hpa -n "$NAMESPACE" --no-headers 2>/dev/null || true
    echo ""
done

FINAL_PODS=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)
log "Final pod count: ${FINAL_PODS} (baseline was: ${BASELINE_PODS})"

if [ "$FINAL_PODS" -le "$BASELINE_PODS" ]; then
    ok "HPA scaled back down to baseline"
elif [ "$FINAL_PODS" -lt "$POST_PODS" ]; then
    ok "HPA is scaling down: ${POST_PODS} → ${FINAL_PODS} (still cooling)"
else
    warn "HPA has not started scaling down yet (stabilizationWindow may still be active)"
fi

echo ""
log "Load test complete."
