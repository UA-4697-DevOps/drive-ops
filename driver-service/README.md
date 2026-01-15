# Driver Service

Python-based microservice for managing drivers and handling trip request notifications.

## Features

- **Driver Management**: CRUD operations for drivers
- **Trip Request Handling**: Receives trip requests and notifies nearby available drivers
- **RabbitMQ Integration**: Consumes `trip.event.created` events from Trip Service
- **Retry Mechanism**: Automatic retry (3 attempts) for failed notification delivery
- **Haversine Search**: Finds drivers within configurable radius using GPS coordinates
- **Comprehensive Logging**: Detailed logs for all operations with trip ID and driver ID tracking

## Architecture
```
Trip Service → RabbitMQ (trip.event.created) → Driver Service
                                                      ↓
                                                Find nearby drivers
                                                      ↓
                                                Send notifications
                                                      ↓
                                                Client Gateway → Driver App
```

## Technology Stack

- **Framework**: FastAPI
- **Language**: Python 3.13
- **Message Broker**: RabbitMQ (pika)
- **HTTP Client**: httpx
- **Validation**: Pydantic
- **Server**: Uvicorn

## Requirements

- Python 3.13+
- RabbitMQ (optional for local development)
- PostgreSQL (when database integration is ready)

## Local Development

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Run the service
```bash
cd src
python -m uvicorn main:app --host 0.0.0.0 --port 8082 --reload
```

The service will be available at `http://localhost:8082`

### 4. Test endpoints
```bash
# Health check
curl http://localhost:8082/health

# List all drivers
curl http://localhost:8082/drivers

# List available drivers
curl "http://localhost:8082/drivers?status=AVAILABLE"

# Send trip request (manual test)
curl -X POST http://localhost:8082/api/v1/trip-requests/send \
  -H "Content-Type: application/json" \
  -d '{
    "trip_id": "test_123",
    "driver_id": "driver_001",
    "pickup": {
      "address": "вул. Хрещатик, 1, Київ",
      "lat": 50.4501,
      "lng": 30.5234
    },
    "dropoff": {
      "address": "Вокзальна площа, Київ",
      "lat": 50.4547,
      "lng": 30.5238
    },
    "passenger_name": "Test User",
    "estimated_distance_km": 5.0,
    "estimated_duration_min": 15,
    "fare_estimate": 100.0
  }'
```

## Docker Deployment

### Build and run with docker-compose
```bash
# From project root
docker-compose up -d driver-service

# Check logs
docker-compose logs -f driver-service

# Stop
docker-compose down
```

### Individual container build
```bash
docker build -t driver-service .
docker run -p 8082:8082 --env-file .env driver-service
```

## API Documentation

### Endpoints

#### Health Check
- **GET** `/health` - Service health status

#### Driver Management
- **GET** `/drivers` - List all drivers (optional `?status=AVAILABLE` filter)
- **GET** `/drivers/{driver_id}` - Get driver by ID
- **POST** `/drivers` - Register new driver
- **POST** `/drivers/{driver_id}/status` - Update driver status
- **POST** `/drivers/{driver_id}/location` - Update driver location

#### Trip Requests (Task #41)
- **POST** `/api/v1/trip-requests/send` - Send trip request to driver (for manual testing)

### Event Consumption

The service consumes `trip.event.created` events from RabbitMQ with the following structure:
```json
{
  "event_id": "uuid",
  "event_type": "trip.event.created",
  "event_version": "1.0",
  "payload": {
    "trip_id": "trip-abc-123",
    "passenger_id": "pass-xyz-789",
    "pickup": {
      "address": "вул. Хрещатик, 1",
      "lat": 50.4501,
      "lng": 30.5234
    },
    "dropoff": {
      "address": "Аеропорт",
      "lat": 50.3450,
      "lng": 30.8947
    }
  }
}
```

## Configuration

Key environment variables:
```bash
# Application
PORT=8082
DEBUG=True

# RabbitMQ
ENABLE_RABBITMQ=false
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
TRIP_EVENTS_QUEUE=trip.events

# Client Gateway
CLIENT_GATEWAY_URL=http://localhost:8080

# Service Settings
MAX_RETRY_ATTEMPTS=3
DRIVER_SEARCH_RADIUS_KM=5.0
MAX_DRIVERS_TO_NOTIFY=10
```

## Project Structure
```
driver-service/
├── src/
│   ├── main.py                          # FastAPI application
│   ├── config.py                        # Configuration settings
│   ├── schemas/
│   │   └── trip_request.py              # Pydantic models
│   ├── services/
│   │   └── driver_notification_service.py  # Business logic
│   ├── repositories/
│   │   └── driver_repository.py         # (Future: DB operations)
│   ├── clients/
│   │   └── gateway_client.py            # HTTP client for Gateway
│   ├── consumers/
│   │   └── trip_events_consumer.py      # RabbitMQ consumer
│   └── utils/
│       └── geo.py                       # Haversine distance calculation
├── tests/
│   └── test_*.py                        # Unit tests
├── requirements.txt                     # Python dependencies
├── Dockerfile                           # Docker configuration
├── .env.example                         # Environment variables template
└── README.md                            # This file
```

## Testing
```bash
# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

## Implementation Details (Task #41)

### Retry Mechanism
- 3 automatic retry attempts for failed notifications
- Exponential backoff between retries (optional future enhancement)
- Detailed logging for each attempt

### Driver Search
- Uses Haversine formula to calculate distance between coordinates
- Configurable search radius (default: 5km)
- Returns drivers sorted by distance
- Only searches AVAILABLE/ONLINE drivers

### Logging
All operations are logged with:
- Trip ID
- Driver ID
- Attempt number (for retries)
- Success/failure status
- Error details

Example log:
```
INFO - Attempting to send trip request - Trip ID: trip_123, Driver ID: driver_001
WARNING - Failed to dispatch trip request (attempt 1/3) - Trip ID: trip_123
ERROR - Failed to dispatch trip request after 3 attempts - Trip ID: trip_123
```

## Integration

### With Trip Service
- Consumes `trip.event.created` events
- Event format matches Trip Service schema (see `trip-service/docs/trip-events.md`)

### With Client Gateway
- Sends HTTP POST to `/api/v1/notifications/driver/{driver_id}`
- Requires Client Gateway to forward notifications to Driver App

### With Database (Future)
- Currently uses in-memory storage for development
- PostgreSQL integration planned with driver-service database team

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

Internal project - UA-4697-DevOps team
