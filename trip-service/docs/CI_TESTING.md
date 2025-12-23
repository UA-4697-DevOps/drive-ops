# TripService CI/CD and Testing

## Overview

The testing system for trip-service includes unit and integration tests. Integration tests use a real PostgreSQL database in a Docker container to verify component interactions.

## Local Development

### Running Unit Tests

Unit tests verify individual components without external dependencies.

```bash
cd trip-service
go test $(go list ./... | grep -v /tests/integration)
```

### Running Integration Tests

**Prerequisites:**
- Docker
- Docker Compose

**Commands:**

```bash
# Start test database
cd trip-service/tests/integration
docker-compose -f docker-compose.test.yml up -d

# Wait for PostgreSQL to be ready (or check status)
docker logs trip-service-test-db

# Run tests
cd ../..
go test -v ./tests/integration/...

# Stop test database
cd tests/integration
docker-compose -f docker-compose.test.yml down -v
```

**Note:** TestMain in `setup_test.go` automatically starts and stops Docker Compose, so these commands can be used for manual setup.

### Running All Tests

```bash
cd trip-service
go test ./...
```

## Integration Test Architecture

### Components

- **PostgreSQL 15** in Docker container
- **Test DB:** `trip_service_test`
- **Port:** `5433` (to avoid conflicts with local PostgreSQL on 5432)
- **Credentials:** `testuser` / `testpass`
- **Container:** `trip-service-test-db`

### What is Tested

1. **Database Connection** (`TestDatabaseConnection`)
   - Verify connection to PostgreSQL
   - Verify database ping

2. **Migrations** (`TestDatabaseMigrations`)
   - Table `trips` exists
   - Enum type `trip_status` created
   - Index `idx_trips_passenger_id` exists

3. **Repository CRUD Operations**
   - `TestTripRepository_Create` - create trip
   - `TestTripRepository_GetByID` - get trip by ID
   - `TestTripRepository_Update` - update trip (status, driver_id)
   - `TestTripRepository_Delete` - delete trip

4. **/health endpoint** (`TestHealthEndpoint`)
   - HTTP request to /health
   - Verify 200 OK and JSON response
   - **NOTE:** Test is skipped until HTTP server is implemented

### Test Isolation

- **Each run** creates a new Docker container
- **No persistent volume** - clean slate every time
- **Each test** cleans its data via `t.Cleanup()`
- **Migrations** are applied automatically in TestMain

### File Structure

```
trip-service/tests/integration/
├── docker-compose.test.yml    # Docker Compose config for test DB
├── setup_test.go               # TestMain, SetupTestDB, RunMigrations, WaitForDB
├── helpers.go                  # Helper functions (CreateTestTrip, AssertTripEqual, etc.)
└── trip_integration_test.go    # All integration tests
```

## CI/CD Pipeline

### Workflow Structure

GitHub Actions workflow contains 3 parallel jobs:

1. **unit-test** - fast unit tests
2. **integration-test** - tests with PostgreSQL
3. **docker-build** - Docker image build

Jobs 2 and 3 run in parallel for speed. Job 1 (unit-test) runs independently.

### Job 1: Unit Test

**What it does:**
- Sets up Go 1.23
- Caches Go modules
- Runs unit tests (excluding integration)

**Command:**
```bash
go test $(go list ./... | grep -v /tests/integration)
```

**Execution time:** ~30 seconds

### Job 2: Integration Test

**What it does:**
1. Sets up Go 1.23
2. Caches Go modules
3. Starts PostgreSQL via docker-compose
4. Waits 10 seconds for DB to be ready
5. Runs integration tests
6. Stops container (even if tests failed)

**Environment Variables:**
```yaml
DB_HOST: localhost
DB_PORT: 5433
DB_USER: testuser
DB_PASSWORD: testpass
DB_NAME: trip_service_test
```

**Command:**
```bash
go test -v ./tests/integration/...
```

**Execution time:** ~1-2 minutes

### Job 3: Docker Build

**What it does:**
1. Sets up Docker Buildx
2. Logs in to GitHub Container Registry (GHCR)
3. Creates metadata for tags
4. Builds Docker image with caching
5. Pushes image (only on main branch, not on PR)

**Image Tags:**
- `main-sha-<commit>` - main branch builds
- `<branch>-sha-<commit>` - feature branch builds
- `pr-<number>` - pull request builds

**Push Strategy:**
- **Main branch:** Push to GHCR
- **Pull requests:** Build only, no push (saves registry space)

**Cache Strategy:**
- Uses GitHub Actions cache for Docker layers
- Significantly speeds up subsequent builds

**NOTE:** This job will work only after `trip-service/Dockerfile` is added.

### Triggers

CI runs on:
- **Push** to any branch with changes in `trip-service/**`
- **Pull Request** with changes in `trip-service/**`

### Caching

**Go Modules:**
- Cache key: `${{ runner.os }}-go-${{ hashFiles('**/go.sum') }}`
- Path: `~/.cache/go-build`, `~/go/pkg/mod`
- Speeds up dependency installation

**Docker Layers:**
- Cache type: GitHub Actions cache (gha)
- Mode: `max` (caches all layers)
- Speeds up Docker builds

## Debug Commands

### Check Test Database

```bash
# Check if container is running
docker ps | grep trip-service-test-db

# View logs
docker logs trip-service-test-db

# Connect to DB
docker exec -it trip-service-test-db psql -U testuser -d trip_service_test

# In psql:
\dt                          # Show tables
\d trips                     # Show table structure
\dT                          # Show types (enum)
\di                          # Show indexes
SELECT * FROM trips;         # Show data
```

### Check Go Environment

```bash
# Go version
go version

# Go environment
go env

# List packages
go list ./...

# Dependencies
go mod graph
go mod verify
```
