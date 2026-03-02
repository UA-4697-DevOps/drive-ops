# Scale Locust workers 1→10 and collect metrics at each step
set -euo pipefail

NAMESPACE="${NAMESPACE:-load-testing}"
APP_NAMESPACE="${APP_NAMESPACE:-default}"
DEPLOYMENT="locust-worker"
REPORT_DIR="./load-test-reports"
USERS_PER_STEP="${USERS_PER_STEP:-50}"
SPAWN_RATE="${SPAWN_RATE:-10}"
STEP_DURATION="${STEP_DURATION:-120}"
MAX_WORKERS=10
LOG_FILE="${REPORT_DIR}/scaling-log-$(date +%Y%m%d-%H%M%S).txt"

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

mkdir -p "$REPORT_DIR"

log()     { echo -e "${CYAN}[$(date '+%H:%M:%S')]${RESET} $*" | tee -a "$LOG_FILE"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET} $*" | tee -a "$LOG_FILE"; }
success() { echo -e "${GREEN}[OK]${RESET} $*" | tee -a "$LOG_FILE"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" | tee -a "$LOG_FILE"; }
header()  {
  echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════${RESET}" | tee -a "$LOG_FILE"
  echo -e "${BOLD}$*${RESET}" | tee -a "$LOG_FILE"
  echo -e "${BOLD}${CYAN}═══════════════════════════════════════${RESET}\n" | tee -a "$LOG_FILE"
}

wait_for_workers() {
  local desired=$1
  log "Waiting for $desired worker pod(s) to be Ready..."
  kubectl rollout status deployment/"$DEPLOYMENT" -n "$NAMESPACE" --timeout=120s
}

collect_metrics() {
  local workers=$1
  local snap="${REPORT_DIR}/snapshot-workers-${workers}-$(date +%H%M%S).txt"
  {
    echo "═══ SNAPSHOT: $workers workers | $(date) ═══"
    echo "── Nodes ──"
    kubectl top nodes 2>/dev/null || echo "(metrics-server unavailable)"
    echo "── Pods: load-testing ──"
    kubectl top pods -n "$NAMESPACE" 2>/dev/null || true
    echo "── Pods: $APP_NAMESPACE ──"
    kubectl top pods -n "$APP_NAMESPACE" 2>/dev/null || true
    echo "── HPA ──"
    kubectl get hpa -n "$APP_NAMESPACE" 2>/dev/null || true
    echo "── Warning Events ──"
    kubectl get events -n "$APP_NAMESPACE" \
      --field-selector type=Warning \
      --sort-by='.lastTimestamp' 2>/dev/null | tail -10 || true
  } | tee "$snap" | tee -a "$LOG_FILE"
}

trigger_locust() {
  local num_users=$1
  kubectl port-forward svc/locust-master -n "$NAMESPACE" 8089:8089 &>/dev/null &
  PF_PID=$!
  sleep 3
  curl -sf -X POST http://localhost:8089/swarm \
    -d "user_count=${num_users}&spawn_rate=${SPAWN_RATE}" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --max-time 10 || warn "Could not trigger Locust API"
  kill $PF_PID 2>/dev/null || true
}

main() {
  header "Drive-Ops Distributed Load Test — Scale 1→$MAX_WORKERS Workers"
  log "users_per_step=$USERS_PER_STEP | spawn_rate=$SPAWN_RATE | step_duration=${STEP_DURATION}s"

  kubectl scale deployment "$DEPLOYMENT" -n "$NAMESPACE" --replicas=1
  wait_for_workers 1

  declare -A BREAKING_POINT

  for workers in $(seq 1 $MAX_WORKERS); do
    header "STEP $workers/$MAX_WORKERS — $workers worker(s)"
    kubectl scale deployment "$DEPLOYMENT" -n "$NAMESPACE" --replicas="$workers"
    wait_for_workers "$workers"

    local total_users=$(( workers * USERS_PER_STEP ))
    trigger_locust "$total_users"
    log "Observing ${STEP_DURATION}s | ~$total_users virtual users..."

    local elapsed=0
    while (( elapsed < STEP_DURATION )); do
      sleep 30; elapsed=$(( elapsed + 30 ))
      collect_metrics "$workers"
      unhealthy=$(kubectl get pods -n "$APP_NAMESPACE" --no-headers 2>/dev/null \
        | grep -cE "CrashLoopBackOff|OOMKilled|Error" || true)
      if (( unhealthy > 0 )); then
        warn "⚠️  $unhealthy unhealthy pod(s) at $workers workers!"
        BREAKING_POINT[$workers]="$unhealthy unhealthy pods @ $total_users users"
      fi
    done
    success "Step $workers complete."
  done

  header "Summary"
  if [[ ${#BREAKING_POINT[@]} -gt 0 ]]; then
    warn "Breaking points detected:"
    for step in "${!BREAKING_POINT[@]}"; do
      warn "  Workers=$step → ${BREAKING_POINT[$step]}"
    done
  else
    success "No breaking points — cluster handled all 10 workers!"
  fi
  kubectl get nodes && kubectl get hpa -n "$APP_NAMESPACE" 2>/dev/null || true
}

main "$@"
