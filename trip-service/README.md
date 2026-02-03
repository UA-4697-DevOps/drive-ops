# Trip Service

REST API service for managing ride trips in the Drive-Ops platform. Handles trip creation, retrieval, driver assignment, and trip lifecycle management.

## Features

- **Trip Management**: Create and retrieve trip requests
- **Driver Assignment**: Assign drivers to pending trips
- **Event Publishing**: Publishes trip events to RabbitMQ for other services
- **Event Consumption**: Consumes driver assignment events
- **Health Checks**: Built-in health endpoint for monitoring
- **API Documentation**: Interactive Swagger/OpenAPI documentation

## Tech Stack

- **Language**: Go 1.25.5
- **Web Framework**: chi v5
- **Database**: PostgreSQL (via GORM)
- **Message Broker**: RabbitMQ
- **API Docs**: Swagger/OpenAPI 2.0 (swaggo/swag)
- **Testing**: testcontainers-go for integration tests

## API Endpoints

| Method | Endpoint                     | Description                      |
|--------|------------------------------|----------------------------------|
| GET    | `/health`                    | Service health check             |
| POST   | `/trips`                     | Create a new trip                |
| GET    | `/trips/{id}`                | Get trip by ID                   |
| PATCH  | `/trips/{id}/assign-driver`  | Assign driver to existing trip   |

### Swagger/OpenAPI Documentation

Trip Service provides interactive API documentation via Swagger UI.

**Quick Start**:
1. Set `ENABLE_SWAGGER=true` in `.env`
2. Start the service: `docker compose up trip-service`
3. Access Swagger UI: http://localhost:8081/swagger/

**Full Documentation**: See [docs/SWAGGER.md](docs/SWAGGER.md) for:
- Local development setup
- AWS deployment access
- Testing with Swagger UI
- Regenerating documentation
- CI/CD integration

## Running Locally

### Prerequisites

- Go 1.25.5+
- PostgreSQL 15+
- RabbitMQ 3.12+
- Docker & Docker Compose (optional)

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password
TRIP_DB_NAME=trip_db

# RabbitMQ
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest

# Server
TRIP_SERVICE_PORT=:8081

# Swagger (dev only)
ENABLE_SWAGGER=true
```

### Option 1: Docker Compose (Recommended)

```bash
# Start all services
docker compose up trip-service

# Start with rebuild
docker compose up --build trip-service

# View logs
docker compose logs -f trip-service
```

### Option 2: Local Go Development

```bash
# Install dependencies
go mod download

# Run migrations
./run-migrations.sh

# Start the service
go run cmd/server/main.go
```

## Database Migrations

Migrations are managed with golang-migrate:

```bash
# Run migrations
./run-migrations.sh

# Create new migration
migrate create -ext sql -dir db/migrations -seq <migration_name>
```

See [docs/MIGRATIONS.MD](docs/MIGRATIONS.MD) for details.

## Testing

### Unit Tests

```bash
go test -v ./internal/repository/...
```

### Integration Tests

Integration tests use testcontainers to spin up PostgreSQL and RabbitMQ:

```bash
# Run all integration tests
go test -v ./tests/integration/...

# Run specific test
go test -v -run TestCreateTrip ./tests/integration/...
```

See [docs/CI_TESTING.md](docs/CI_TESTING.md) for CI/CD testing details.

## Project Structure

```
trip-service/
├── cmd/
│   └── server/
│       └── main.go              # Application entry point
├── internal/
│   ├── api/
│   │   └── http/
│   │       └── handler.go       # HTTP handlers with Swagger annotations
│   ├── broker/
│   │   ├── publisher.go         # RabbitMQ publisher
│   │   ├── consumer.go          # RabbitMQ consumer
│   │   └── events.go            # Event definitions
│   ├── domain/
│   │   ├── trip.go              # Domain models
│   │   └── events.go            # Domain events
│   ├── repository/
│   │   └── trip_repository.go   # Database layer (GORM)
│   └── service/
│       └── trip_service.go      # Business logic
├── db/
│   └── migrations/              # SQL migrations
├── docs/
│   ├── swagger.json             # Generated OpenAPI spec
│   ├── swagger.yaml             # Generated OpenAPI spec (YAML)
│   ├── docs.go                  # Generated Go swagger docs
│   ├── SWAGGER.md               # Swagger documentation
│   └── MIGRATIONS.MD            # Migration guide
├── tests/
│   └── integration/             # Integration tests
├── Dockerfile                   # Production Docker image
├── Dockerfile.migrations        # Migration runner image
└── go.mod                       # Go dependencies
```

## API Documentation Generation

When you modify API endpoints or add new ones, regenerate the OpenAPI spec:

```bash
# Install swag
go install github.com/swaggo/swag/cmd/swag@latest

# Generate documentation
swag init -g cmd/server/main.go -o docs

# Commit the changes
git add docs/
git commit -m "Update OpenAPI spec"
```

The CI pipeline will fail if the committed spec doesn't match the code.

## Docker Build

```bash
# Build image
docker build -t trip-service:latest .

# Run container
docker run -p 8081:8081 --env-file .env trip-service:latest
```

## CI/CD

The GitHub Actions workflow (`.github/workflows/trip-service-ci.yml`) includes:

1. **Linting**: golangci-lint
2. **Swagger Validation**: Ensures OpenAPI spec is valid and up-to-date
3. **Unit Tests**: Repository layer tests
4. **Integration Tests**: Full stack tests with PostgreSQL and RabbitMQ
5. **Docker Build**: Builds and caches the Docker image

## Deployment

### AWS Development Environment

Trip Service can be deployed on:
- **ECS Fargate**: Container orchestration
- **EC2 with Docker**: Direct container deployment

**Environment Variables** (ECS Task Definition or EC2):
- Set `ENABLE_SWAGGER=true` for dev environments
- Set `ENABLE_SWAGGER=false` (or unset) for production

**Accessing Swagger UI**:
- Via ALB: `https://<alb-dns>/swagger/`
- Via Port Forwarding: See [docs/SWAGGER.md](docs/SWAGGER.md)

## Health Checks

The service exposes a health endpoint:

```bash
curl http://localhost:8081/health
```

Response:
```json
{"status":"ok"}
```

## Event Architecture

Trip Service participates in an event-driven architecture:

**Published Events** (to RabbitMQ):
- `trip.created`: When a new trip is created
- `trip.driver_assigned`: When a driver is assigned

**Consumed Events** (from RabbitMQ):
- `driver.assigned`: Updates trip with driver information

See [docs/trip-events.md](docs/trip-events.md) for event schemas.

## Security

- Non-root container user (`appuser`)
- No hardcoded secrets (use environment variables)
- Input validation on all endpoints
- SQL injection protection via GORM
- Swagger UI disabled by default in production

## Contributing

1. Create a feature branch
2. Make changes and add tests
3. Run linting: `golangci-lint run`
4. Run tests: `go test ./...`
5. Update API docs if needed: `swag init -g cmd/server/main.go -o docs`
6. Submit a pull request

## Troubleshooting

### Cannot connect to database

- Check `DB_HOST` and `DB_PORT` in `.env`
- Ensure PostgreSQL is running
- Verify network connectivity (Docker network for containers)

### RabbitMQ connection fails

- Check `RABBITMQ_HOST` and `RABBITMQ_PORT`
- Ensure RabbitMQ is running
- Check credentials in `.env`

### Swagger UI returns 404

- Ensure `ENABLE_SWAGGER=true` is set
- Restart the service
- Check logs for "Swagger UI enabled" message

## License

Apache 2.0

## Support

For issues and questions:
- Check [docs/CI_TESTING.md](docs/CI_TESTING.md)
- Check [docs/SWAGGER.md](docs/SWAGGER.md)
- Contact: Drive-Ops Team
