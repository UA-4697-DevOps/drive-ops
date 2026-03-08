# Trip Service – Performance Baseline

Performance targets and scaling behavior documentation for the Trip Service.

## Baseline Metrics

| Metric | Target | Notes |
|---|---|---|
| **p50 latency** | < 100 ms | Median response time under normal load |
| **p95 latency** | < 500 ms | Tail latency during peak traffic |
| **p99 latency** | < 1,000 ms | Worst-case latency |
| **Error rate** | < 1% | HTTP 5xx / connection failures |
| **Throughput** | ~200 RPS / pod | Estimated at CPU request of 100m |

## HPA Configuration

| Environment | Min Replicas | Max Replicas | CPU Target | Memory Target |
|---|---|---|---|---|
| **Dev** | 1 | 5 | 70% | 80% |
| **Staging** | 2 | 8 | 70% | 80% |
| **Production** | 3 | 10 | 65% | 75% |

### Scaling Behavior
- **Scale-up**: 60s stabilization window, up to 100% increase or 4 pods per 60s (whichever is larger)
- **Scale-down**: 300s stabilization window, max 25% decrease per 120s (prevents flapping)

## Resource Allocation

| Environment | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---|---|---|---|---|
| **Dev** | 100m | 500m | 128Mi | 512Mi |
| **Staging** | 100m | 500m | 128Mi | 512Mi |
| **Production** | 150m | 500m | 192Mi | 512Mi |

## Running the Load Test

### Local (requires k6 installed)
```bash
k6 run tests/load/load-test.js
```

### In-Cluster (Kubernetes Job)
```bash
# 1. Create ConfigMap with the test script
kubectl create configmap k6-load-test \
  --from-file=load-test.js=tests/load/load-test.js \
  -n dev

# 2. Run the load test Job
kubectl apply -f tests/load/k6-job.yaml

# 3. Follow logs
kubectl logs -n dev -l job-name=k6-trip-service-load-test -f
```

### Load Test Stages

| Stage | Duration | Virtual Users | Purpose |
|---|---|---|---|
| Warm-up | 2 min | Ramp to 50 | Gradual ramp to baseline |
| Peak | 3 min | Ramp to 100 | Sustained load for HPA trigger |
| Cool-down | 2 min | Ramp down to 50 | Observe scale-down behavior |
| Drain | 1 min | Ramp to 0 | Complete wind-down |

## Monitoring Commands

### HPA Status
```bash
# Watch HPA scaling in real-time
kubectl get hpa -n dev -w

# Detailed HPA status with conditions
kubectl describe hpa trip-service -n dev
```

### Cluster Autoscaler
```bash
# View Cluster Autoscaler decisions
kubectl logs -n kube-system -l k8s-app=cluster-autoscaler -f --tail=50

# Check node scaling events
kubectl get events -n kube-system --field-selector reason=ScaleUp
kubectl get events -n kube-system --field-selector reason=ScaleDown
```

### Pod Resource Usage
```bash
# Current pod CPU/memory usage (requires metrics-server)
kubectl top pods -n dev -l app=trip-service

# Node-level resource usage
kubectl top nodes
```

## Expected Scaling Behavior

1. **Idle** → 2 pods (minReplicas in dev is 1, staging/prod ≥ 2)
2. **Light load** (~50 VUs) → 2-3 pods, CPU utilization ~40-50%
3. **Peak load** (~100 VUs) → 4-6 pods, CPU utilization ~65-80%
4. **After scale-down** (5+ min cooldown) → returns to minReplicas

## Updating This Baseline

After running the load test, update the **Baseline Metrics** table with actual observed values:

```bash
# Results are written to stdout and /tmp/k6-results.json in the Job pod
kubectl logs -n dev -l job-name=k6-trip-service-load-test | tail -20
```
