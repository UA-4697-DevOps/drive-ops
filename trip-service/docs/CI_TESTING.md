# TripService CI/CD and Testing

## Overview

The testing system for trip-service includes unit tests, integration tests, and end-to-end tests. Integration tests use a real PostgreSQL database in Docker to verify component interactions and can run in multiple environments (local, CI).

## Local Development

### Prerequisites

- **Go 1.24+**
- **Docker** and **Docker Compose**
- **golangci-lint** (for linting)

### Running Linter

The project uses golangci-lint for code quality checks.

**Install:**
```bash
# macOS
brew install golangci-lint

# Linux / Others
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
```

**Run:**
```bash
cd trip-service

# Basic run
golangci-lint run

# With auto-fix (where possible)
golangci-lint run --fix

# Verbose output
golangci-lint run -v
```

### Running Unit Tests

Unit tests verify individual components in isolation. Tests in `internal/repository` use Testcontainers and require Docker.

```bash
cd trip-service

# Run all unit tests (excludes integration)
go test -v $(go list ./... | grep -v /tests/integration)

# Run specific package
go test -v ./internal/repository/...
```

### Running Integration Tests

Integration tests can run in **two modes**:

#### Mode 1: Automatic (Recommended)

Tests automatically start docker-compose if needed:

```bash
cd trip-service
go test -v ./tests/integration/...
```

**What happens:**
1. Tests detect no database is running
2. Auto-start `docker-compose.test.yml` (test DB on port 5433)
3. Run migrations
4. Execute tests
5. Cleanup and stop Docker Compose

#### Mode 2: Manual Setup

Start test database manually:

```bash
# Terminal 1: Start test database
cd trip-service/tests/integration
docker compose -f docker-compose.test.yml up -d

# Terminal 2: Run tests
cd trip-service
go test -v ./tests/integration/...

# Cleanup
cd tests/integration
docker compose -f docker-compose.test.yml down -v
```

#### Mode 3: Full Stack (E2E Testing)

Test against the complete running service:

```bash
# Terminal 1: Start full stack
cd trip-service
docker compose up -d

# Terminal 2: Run tests (including health endpoint)
go test -v ./tests/integration/...

# Cleanup
docker compose down -v
```

### Running All Tests

```bash
cd trip-service
go test -v ./...
```

## Test Architecture

### Two Docker Compose Files

| File | Purpose | Database Port | Use Case |
|------|---------|---------------|----------|
| `docker-compose.yaml` | Full production stack | 5432 | Local dev, E2E testing, CI |
| `docker-compose.test.yml` | Test database only | 5433 | Fast integration tests |

**Why both?**
- **No port conflicts** - Can run dev server (5432) and tests (5433) simultaneously
- **Faster test cycles** - Test-only DB starts in ~2s vs full stack ~15s
- **Flexibility** - Choose appropriate setup for the task

### Integration Test Components

**Test Database (docker-compose.test.yml):**
- PostgreSQL 15-alpine
- Port: 5433
- Database: `trip_service_test`
- Credentials: `testuser` / `testpass`

**Full Stack (docker-compose.yaml):**
- PostgreSQL 15-alpine (port 5432)
- trip-migrations service (applies SQL migrations)
- trip-service HTTP server (port 5002)
- Database: `trips`, credentials: `vagrant` / `trips`

### What is Tested

1. **Database Connection** (`TestDatabaseConnection`)
   - Verify PostgreSQL connectivity
   - Verify database ping

2. **Database Migrations** (`TestDatabaseMigrations`)
   - Table `trips` exists
   - Enum type `trip_status` created
   - Index `idx_trips_passenger_id` exists

3. **Repository CRUD Operations**
   - `TestTripRepository_Create` - create trip
   - `TestTripRepository_GetByID` - retrieve by ID
   - `TestTripRepository_Update` - update status/driver
   - `TestTripRepository_Delete` - delete trip

4. **HTTP Health Endpoint** (`TestHealthEndpoint`)
   - GET /health returns 200 OK
   - Response is valid JSON: `{"status":"ok"}`
   - **Requires:** trip-service HTTP server running

### Environment-Aware Test Setup

Tests automatically detect the environment:

```go
// In TestMain (setup_test.go):
// 1. Try to connect to database
// 2. If fails: start docker-compose.test.yml
// 3. If succeeds: use existing database (CI scenario)
```

**Benefits:**
- **Local:** Auto-manages test database
- **CI:** Uses full stack started by workflow
- **No manual configuration needed**

### Test Isolation

- Each test run creates fresh state
- No persistent volumes (clean slate)
- Each test uses `t.Cleanup()` for data cleanup
- Migrations: Auto-applied or skipped if already present

### Database Configuration

The service supports two database configuration modes:

**1. DB_URL (Docker/Production):**
```bash
DB_URL=postgres://user:pass@host:5432/dbname?sslmode=disable
```

**2. Individual Environment Variables (Local Development):**
```bash
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=trip_db
```

The service in `cmd/main.go` tries DB_URL first, falls back to individual vars.

## CI/CD Pipeline

### Workflow Structure

GitHub Actions workflow: `.github/workflows/trip-service-ci.yml`

**Jobs:**
1. `lint` - Code quality checks
2. `unit-test` - Fast unit tests
3. `integration-test` - E2E tests with full stack
4. `docker-build` - Docker image build

**Dependencies:**
- `unit-test` depends on `lint`
- `integration-test` depends on `unit-test`
- `docker-build` depends on `unit-test` and `integration-test`

### Job 1: Lint

**What it does:**
- Runs golangci-lint with latest version
- Checks code quality, formatting, common errors
- Fails pipeline if linting errors found

**Linters enabled:**
- errcheck (unchecked errors)
- staticcheck (static analysis)
- gosimple, unused, ineffassign, and more

**Execution time:** ~20-30 seconds

### Job 2: Unit Test

**What it does:**
- Sets up Go 1.24
- Caches Go modules
- Runs unit tests (excluding integration tests)

**Command:**
```bash
go test -v ./internal/repository/...
```

**Execution time:** ~30-60 seconds

### Job 3: Integration Test (E2E)

**What it does:**
1. Starts **full trip-service stack** via `docker compose up -d`
2. Waits for services to become healthy (health checks)
3. Verifies `/health` endpoint responds correctly
4. Runs all integration tests (including TestHealthEndpoint)
5. Shows logs on failure
6. Cleanup: `docker compose down -v`

**Services started:**
- PostgreSQL database (port 5432)
- trip-migrations (applies SQL migrations)
- trip-service HTTP server (port 5002)

**Health Check:**
```bash
curl -f http://localhost:5002/health
# Expected: {"status":"ok"}
```

**Environment Variables:**
```yaml
DB_HOST: localhost
DB_PORT: 5432
DB_USER: vagrant
DB_PASSWORD: trips
DB_NAME: trips
SERVICE_URL: http://localhost:5002
```

**Test Command:**
```bash
go test -v -race -tags=integration ./tests/integration/...
```

**Key Features:**
- Runs tests with race detector (`-race`)
- Tests actual HTTP server (E2E)
- Comprehensive error logging if tests fail
- Timeout protection (90s for service health)

**Execution time:** ~2-3 minutes

### Job 4: Docker Build

**What it does:**
1. Sets up Docker Buildx
2. Logs in to GitHub Container Registry (GHCR)
3. Extracts metadata for image tags
4. Builds Docker image with layer caching
5. Pushes image (disabled by default: `push: false`)

**Image Tags:**
- `<branch>-sha-<commit>` - branch builds
- `pr-<number>` - pull request builds

**Push Strategy:**
- Currently disabled (`push: false`)
- Can enable with: `push: ${{ github.event_name != 'pull_request' }}`

**Cache Strategy:**
- GitHub Actions cache for Docker layers
- Mode: `max` (caches all layers)
- Speeds up subsequent builds

**Execution time:** ~1-2 minutes (with cache)

### Triggers

CI runs on:
- **Push** to `main` or `trip-service` branches with changes in `trip-service/**`
- **Pull Request** to `main` with changes in `trip-service/**`
- Changes to `.github/workflows/trip-service-ci.yml`

### Concurrency

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

**Benefit:** Cancels old runs when new commits are pushed

### Caching

**Go Modules:**
- Key: `${{ runner.os }}-go-${{ hashFiles('**/go.sum') }}`
- Paths: `~/.cache/go-build`, `~/go/pkg/mod`
- Invalidates when dependencies change

**Docker Layers:**
- Type: GitHub Actions cache
- Shared across builds
- Significantly speeds up image builds

## File Structure

```text
trip-service/
├── cmd/
│   └── main.go                      # Entry point, DB_URL support
├── internal/
│   ├── api/http/
│   │   └── handler.go               # HTTP handlers (/health, /trips)
│   ├── domain/
│   │   └── trip.go                  # Trip entity
│   ├── repository/
│   │   ├── trip_repository.go       # GORM repository
│   │   └── trip_repository_test.go  # Unit tests (testcontainers)
│   └── service/
│       └── trip_service.go          # Business logic
├── tests/integration/
│   ├── docker-compose.test.yml      # Test database setup
│   ├── setup_test.go                # TestMain, environment-aware setup
│   ├── helpers.go                   # Test utilities
│   └── trip_integration_test.go     # Integration tests
├── db/migrations/
│   └── 001_init_trips.up.sql        # SQL migrations
├── docker-compose.yaml              # Full production stack
├── Dockerfile                       # Service container image
├── Dockerfile.migrations            # Migration runner image
└── docs/
    └── CI_TESTING.md                # This file
```

## Troubleshooting

### Port Already in Use

**Error:** `bind: address already in use`

**Solution:**
```bash
# Check what's using the port
lsof -i :5432
lsof -i :5433
lsof -i :5002

# Stop conflicting services
docker compose down  # In trip-service/
# or
docker compose -f tests/integration/docker-compose.test.yml down
```

### Docker Not Running

**Error:** `Cannot connect to the Docker daemon`

**Solution:**
```bash
# macOS
open -a Docker

# Linux
sudo systemctl start docker

# Verify
docker ps
```

### Migrations Fail: "type already exists"

**Error:** `ERROR: type "trip_status" already exists`

**Cause:** Migrations already applied by trip-migrations service

**Solution:** Tests now automatically detect and skip already-applied migrations. If error persists:
```bash
# Clean database
docker compose down -v  # -v removes volumes
docker compose up -d
```

### Tests Can't Connect to Database

**Error:** `connection refused`

**Check:**
1. Is Docker running? `docker ps`
2. Is database healthy? `docker compose ps`
3. Correct port? Test DB uses 5433, main DB uses 5432
4. Check logs: `docker compose logs db`

**Debug:**
```bash
# Connect manually
docker exec -it trip-service-test-db psql -U testuser -d trip_service_test

# Or for main DB
docker exec -it trip-service-db-1 psql -U vagrant -d trips
```

### Linter Errors

**Error:** `golangci-lint: command not found`

**Solution:**
```bash
# Install
brew install golangci-lint  # macOS
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest

# Verify
golangci-lint --version
```

### Health Endpoint Test Fails

**Error:** `TestHealthEndpoint: connection refused`

**Cause:** trip-service HTTP server not running

**Solution:**
```bash
# Start full stack
cd trip-service
docker compose up -d

# Wait for health
curl http://localhost:5002/health

# Run tests
go test -v ./tests/integration/...
```

## Best Practices

### For Developers

1. **Run linter before commit:**
   ```bash
   golangci-lint run --fix
   ```

2. **Run integration tests locally before PR:**
   ```bash
   go test -v ./tests/integration/...
   ```

3. **Use appropriate docker-compose:**
   - Quick tests → `docker-compose.test.yml` (port 5433)
   - E2E testing → `docker-compose.yaml` (full stack)

4. **Clean up containers:**
   ```bash
   docker compose down -v  # Always use -v to remove volumes
   ```

### For CI

1. **Commit messages:** Follow Conventional Commits format
2. **Test isolation:** Each test cleans its own data
3. **Error handling:** Always check error returns (linter enforces this)
4. **Health checks:** Verify service health before running E2E tests

## Performance

### Typical Execution Times

| Operation | Local | CI |
|-----------|-------|-----|
| Lint | 20s | 30s |
| Unit tests | 30s | 60s |
| Integration tests (test DB only) | 8s | 15s |
| Integration tests (full stack) | 20s | 2-3min |
| Docker build | 30s (cached) | 1-2min |
| **Total CI pipeline** | N/A | **~4-5 minutes** |

### Optimization Tips

- Go module cache speeds up dependency installation
- Docker layer cache reduces build time by 50-80%
- Parallel job execution where possible
- Cancel outdated runs with concurrency groups

## Additional Resources

- [Go Testing Guide](https://go.dev/doc/tutorial/add-a-test)
- [Testcontainers for Go](https://golang.testcontainers.org/)
- [golangci-lint Documentation](https://golangci-lint.run/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
