# Trip Service — Deployment Summary

Reference document for the final milestone presentation.

## Architecture

```
                  ┌──────────────┐
                  │  Web Client  │
                  └──────┬───────┘
                         │ HTTP
                  ┌──────▼───────┐
                  │Client Gateway│
                  └──────┬───────┘
                         │ REST
           ┌─────────────▼──────────────┐
           │       Trip Service         │
           │  (Go / Chi / Gorm / OTel)  │
           └──┬──────────┬──────────┬───┘
              │          │          │
         SQS FIFO   SQS FIFO   PostgreSQL
      trip-created driver-assigned   (RDS)
              │          │
       ┌──────▼──────────▼──────┐
       │    Driver Service      │
       │    (Python / FastAPI)  │
       └────────────────────────┘
```

## Deployment Flow

1. **Code → GitHub** — PR triggers CI pipeline
2. **CI Pipeline** (`trip-service-ci.yml`):
   - Lint (golangci-lint) → Swagger validation → Unit tests → Integration tests → ECR push
   - On merge to `main`: builds Docker image, pushes SHA-tagged image to ECR, updates `values-dev.yaml`
3. **ECR → ArgoCD** — ArgoCD watches `trip-service/charts/trip-service` with `values-dev.yaml`
4. **ArgoCD → EKS** — Auto-syncs Helm chart to `trip-service` namespace

Manual deploy also available via `deploy-trip-service.yml` (workflow_dispatch with custom tag).

## Key Configuration

| Component | Source |
|-----------|--------|
| **Image tag** | `values-dev.yaml` → `image.tag` (updated by CI) |
| **DB credentials** | AWS Secrets Manager → ExternalSecret → `trip-service-secrets` |
| **SQS URLs** | ConfigMap via `config.*` in Helm values |
| **IAM permissions** | IRSA via ServiceAccount annotation |
| **Scaling** | HPA: 1–5 replicas, 70% CPU / 80% memory targets |

## Health Verification

```bash
# Pod status
kubectl -n trip-service get pods

# Health check
kubectl -n trip-service exec -it <pod> -- curl http://localhost:8081/health

# IRSA binding
kubectl -n trip-service describe sa trip-service

# Logs
kubectl -n trip-service logs -l app=trip-service -f

# ArgoCD sync status
argocd app get trip-service
```

## Observability

- **Metrics**: Prometheus scrapes `/metrics` (request rate, latency, error rate, goroutines, heap)
- **Tracing**: OpenTelemetry → Jaeger (`jaeger.monitoring.svc.cluster.local:4317`)
- **Dashboard**: Grafana — "Trip Service KPIs" (auto-loaded from ConfigMap)
