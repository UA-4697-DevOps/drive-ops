# Drive-Ops Smoke Tests

Automated smoke tests to verify infrastructure and services availability after AWS deployment.

## Quick Start

```bash
# Start services in Docker
docker-compose up -d

# Wait for services to start (30-60 seconds)
sleep 30

# Install dependencies
pip install -r requirements.txt

# Run health check
python health_check.py
```

## Testing with Docker

When services are running in Docker, they are available on localhost:

```bash
# Check that services are running
docker ps

# Run smoke tests
export SMOKE_TRIP_SERVICE_URL=http://localhost:8081
export SMOKE_DRIVER_SERVICE_URL=http://localhost:8082
export SMOKE_CLIENT_GATEWAY_URL=http://localhost:8080

python health_check.py
```

## Available Tests

### 1. Health Check (`health_check.py`)

Verifies availability of all services through their health endpoints.

**What it checks:**
- Trip Service: `GET /health` → HTTP 200 + `{"status":"ok"}`
- Driver Service: `GET /health` → HTTP 200 + `{"status":"ok"}`
- Client Gateway: `GET /` → HTTP 200 + `{"status":"ok"}`

**Environment Variables:**
- `SMOKE_TRIP_SERVICE_URL` - Trip Service URL (required)
- `SMOKE_DRIVER_SERVICE_URL` - Driver Service URL (required)
- `SMOKE_CLIENT_GATEWAY_URL` - Client Gateway URL (required)

**Retry Logic:**
- Timeout: 10 seconds per request
- Retries: 3 attempts with 5-second intervals

**Exit Codes:**
- `0` - all services are healthy
- `1` - at least one service is unavailable

**Output Example:**
```text
======================================================================
  Drive-Ops Health Check Smoke Test
======================================================================

Running health checks...

  Checking Trip Service... ✅
  Checking Driver Service... ✅
  Checking Client Gateway... ✅

Results:

Service              Status          Details
----------------------------------------------------------------------
Trip Service         ✅ OK           trip-service.example.com:8081/health
Driver Service       ✅ OK           driver-service.example.com:8082/health
Client Gateway       ✅ OK           client-gateway.example.com:8080/
----------------------------------------------------------------------

✅ All services are healthy!
```

### 2. RDS Connectivity (planned)

**TODO:** Verifies write/read operations with PostgreSQL.

## Usage in Different Environments

### Development
```bash
export SMOKE_TRIP_SERVICE_URL=http://localhost:8081
export SMOKE_DRIVER_SERVICE_URL=http://localhost:8082
export SMOKE_CLIENT_GATEWAY_URL=http://localhost:8080

python health_check.py
```

### Staging/Production
```bash
# Use AWS hosts
export SMOKE_TRIP_SERVICE_URL=http://trip-service-staging.internal:8081
export SMOKE_DRIVER_SERVICE_URL=http://driver-service-staging.internal:8082
export SMOKE_CLIENT_GATEWAY_URL=http://gateway-staging.internal:8080

python health_check.py
```

## CI/CD Integration

Smoke tests can be run after deployment via GitHub Actions:

```yaml
- name: Run Smoke Tests
  env:
    SMOKE_TRIP_SERVICE_URL: ${{ secrets.SMOKE_TRIP_SERVICE_URL }}
    SMOKE_DRIVER_SERVICE_URL: ${{ secrets.SMOKE_DRIVER_SERVICE_URL }}
    SMOKE_CLIENT_GATEWAY_URL: ${{ secrets.SMOKE_CLIENT_GATEWAY_URL }}
  run: |
    cd infra/scripts/smoke-tests
    pip install -r requirements.txt
    python health_check.py
```

## Troubleshooting

### Connection Timeout
```text
❌ Timeout after 10s (tried 3 times)
```
**Possible Causes:**
- Service is not running
- Incorrect URL or port
- Firewall/Security Group blocks connection
- Service takes too long to start

**Solutions:**
1. Check container status: `docker ps` or `kubectl get pods`
2. Check logs: `docker logs <container>` or `kubectl logs <pod>`
3. Check Security Groups in AWS
4. Try curl manually: `curl -v http://<service-url>/health`

### Connection Refused
```text
❌ Connection error: Connection refused
```
**Possible Causes:**
- Service is not listening on the specified port
- Incorrect port in URL

**Solutions:**
1. Verify service is running: `netstat -tulpn | grep <port>`
2. Check port configuration in Dockerfile/docker-compose.yml

### Invalid JSON Response
```text
❌ Invalid response: {"status": "error"}
```
**Possible Causes:**
- Service is running but has dependency issues (DB, SQS)
- Health endpoint returns an error

**Solutions:**
1. Check service logs
2. Verify PostgreSQL and SQS connectivity
3. See failure diagnostics documentation

## Additional Information

For detailed information on common failures and their fixes, see:
- [Failure Modes Guide](../../docs/FAILURE_MODES.md) — diagnostics for IAM, SG, SQS, RDS, VPC failures
