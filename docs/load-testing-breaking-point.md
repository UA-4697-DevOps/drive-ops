# Load Testing — Breaking Point Report

## Environment

| Parameter | Value |
|-----------|-------|
| Cluster | AWS EKS (us-east-2) |
| Namespace | dev |
| Target service | trip-service |
| Test tool | Locust 2.32.3 |
| Test date | <!-- FILL: YYYY-MM-DD --> |

---

## Test Configuration

| Parameter | Value |
|-----------|-------|
| Users per worker step | 50 |
| Spawn rate | 10 users/s |
| Step duration | 120s |
| Max workers | 10 |
| Max virtual users | 500 |

---

## Endpoint Load Profile

| Endpoint | Weight | Description |
|----------|--------|-------------|
| POST /trips | 5x | Create trip request |
| GET /trips/{id} | 3x | Get trip by ID |
| GET /health | 1x | Health check |
| PATCH /trips/{id}/assign-driver | 1x | Assign driver |

---

## Results by Worker Count

| Workers | Virtual Users | Avg RPS | P95 Latency (ms) | Error Rate (%) | CPU (node) | Memory | Status |
|---------|--------------|---------|------------------|----------------|------------|--------|--------|
| 1 | 50 | | | | | | |
| 2 | 100 | | | | | | |
| 3 | 150 | | | | | | |
| 4 | 200 | | | | | | |
| 5 | 250 | | | | | | |
| 6 | 300 | | | | | | |
| 7 | 350 | | | | | | |
| 8 | 400 | | | | | | |
| 9 | 450 | | | | | | |
| 10 | 500 | | | | | | |

---

## Breaking Point

**Identified at:** <!-- FILL: N workers / N virtual users -->

### Symptoms observed

- [ ] Latency spike — P95 exceeded 2000ms
- [ ] Error rate exceeded 5%
- [ ] DB saturation — connection pool exhausted
- [ ] OOMKilled pods
- [ ] CrashLoopBackOff
- [ ] HPA hit maxReplicas limit
- [ ] Cluster Autoscaler triggered new node

### Details
```text
# Paste kubectl top nodes output at breaking point
```
```text
# Paste kubectl get hpa output at breaking point
```
```text
# Paste relevant kubectl get events output
```

---

## HPA Validation

### trip-service HPA behavior

| Workers | HPA Replicas (min→max observed) | Trigger | Notes |
|---------|--------------------------------|---------|-------|
| 1-3 | | | |
| 4-6 | | | |
| 7-10 | | | |

**HPA scaled successfully:** Yes / No  
**Max replicas reached:** Yes / No — at N workers

---

## Cluster Autoscaler Validation

**New node provisioned:** Yes / No  
**At worker count:** <!-- FILL -->  
**Node provisioning time:** <!-- FILL --> seconds  

---

## Conclusions

<!-- FILL after running the test -->

**Stable range:** up to N workers (N virtual users)  
**Degradation starts:** at N workers  
**Complete failure:** at N workers  

### Recommendations

1. <!-- e.g. Increase DB connection pool (currently max 25) -->
2. <!-- e.g. Add read replica for GET /trips queries -->
3. <!-- e.g. Tune HPA minReplicas to 2 for production -->
