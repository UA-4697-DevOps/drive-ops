# Driver Service

Python-based microservice for managing drivers and handling trip request notifications.

## Features

- **Driver Management**: CRUD operations for drivers
- **Trip Request Handling**: Receives trip requests and notifies nearby available drivers
- **Driver Response Processing**: Handles driver accept/reject responses and publishes assignment events *(NEW in v0.2.0)*
- **RabbitMQ Integration**: Consumes `trip.event.created` and `driver.cmd.trip_accept/reject` events
- **Event Publishing**: Publishes `trip.event.driver_assigned` to Trip Service *(NEW in v0.2.0)*
- **Idempotency**: Prevents duplicate processing of driver responses *(NEW in v0.2.0)*
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
                                        Client Gateway → Telegram Bot → Driver
                                                                          ↓
                                        driver.cmd.trip_accept/reject ←──┘
                                                      ↓
                                            DriverResponseConsumer
                                                      ↓
                                            [Validate & Process]
                                                      ↓
                                        trip.event.driver_assigned
                                                      ↓
                                                Trip Service
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
python -m uvicorn main:app --reload --port 8082 --app-dir src
```

The service will be available at `http://localhost:8082`

### 4. Test endpoints
```bash
# Health check
curl http://localhost:8082/health

# Service info (check version and features)
curl http://localhost:8082/

# List all drivers
curl http://localhost:8082/drivers

# List available drivers
curl "http://localhost:8082/drivers?status=AVAILABLE"

# List trip requests (NEW)
curl http://localhost:8082/api/v1/trip-requests

# Get specific trip request (NEW)
curl http://localhost:8082/api/v1/trip-requests/trip_123

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
### Interactive Swagger UI (OAS 3.1)
To facilitate testing and integration, the Driver Service provides a self-documenting API:
- **Local**: [http://localhost:8082/docs](http://localhost:8082/docs)
- **AWS Dev**: `http://<aws-dev-host>:8082/docs` (Available when `DEBUG=True`)
- **OpenAPI Spec**: `/openapi.json`


### Endpoints

#### Health Check
- **GET** `/health` - Service health status
- **GET** `/` - Service information (version, features)

#### Driver Management
- **GET** `/drivers` - List all drivers (optional `?status=AVAILABLE` filter)
- **GET** `/drivers/{driver_id}` - Get driver by ID
- **POST** `/drivers` - Register new driver
- **POST** `/drivers/{driver_id}/status` - Update driver status
- **POST** `/drivers/{driver_id}/location` - Update driver location

#### Trip Requests (Task #41)
- **POST** `/api/v1/trip-requests/send` - Send trip request to driver (for manual testing)

#### Trip Request Monitoring (Task #42 - NEW)
- **GET** `/api/v1/trip-requests` - List all tracked trip requests
- **GET** `/api/v1/trip-requests/{trip_id}` - Get specific trip request details

### Event Consumption

#### trip.event.created (Task #41)
The service consumes `trip.event.created` events from RabbitMQ:
```json
{
  "event_type": "trip.event.created",
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

#### driver.cmd.trip_accept / driver.cmd.trip_reject (Task #42 - NEW)
The service consumes driver response events:
```json
{
  "event_type": "driver.cmd.trip_accept",
  "payload": {
    "driver_id": "driver_001",
    "trip_id": "trip_123",
    "decision": "accept",
    "timestamp": "2026-01-17T19:30:00Z"
  }
}
```

### Event Publishing (Task #42 - NEW)

#### trip.event.driver_assigned
Published when driver accepts trip request:
```json
{
  "event_type": "trip.event.driver_assigned",
  "payload": {
    "trip_id": "trip_123",
    "driver_id": "driver_001",
    "assigned_at": "2026-01-17T19:30:00Z"
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
DRIVER_RESPONSES_QUEUE=driver.responses      # NEW in v0.2.0
TRIP_EVENTS_EXCHANGE=trip.events             # NEW in v0.2.0

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
│   ├── main.py                               # FastAPI application
│   ├── config.py                             # Configuration settings
│   ├── schemas/
│   │   ├── trip_request.py                   # Trip request models
│   │   └── driver_response.py                # Driver response models (NEW)
│   ├── services/
│   │   ├── driver_notification_service.py    # Trip request notifications
│   │   └── driver_response_service.py        # Driver response handling (NEW)
│   ├── clients/
│   │   ├── gateway_client.py                 # HTTP client for Gateway
│   │   └── rabbitmq_publisher.py             # RabbitMQ event publisher (NEW)
│   ├── consumers/
│   │   ├── trip_events_consumer.py           # Consumes trip.event.created
│   │   └── driver_response_consumer.py       # Consumes driver responses (NEW)
│   └── utils/
│       └── geo.py                            # Haversine distance calculation
├── tests/
│   └── test_*.py                             # Unit tests
├── requirements.txt                          # Python dependencies
├── Dockerfile                                # Docker configuration
├── .env.example                              # Environment variables template
└── README.md                                 # This file
```

## Testing
```bash
# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

## Implementation Details

### Task #41: Trip Request Handling

#### Retry Mechanism
- 3 automatic retry attempts for failed notifications
- Exponential backoff between retries (optional future enhancement)
- Detailed logging for each attempt

#### Driver Search
- Uses Haversine formula to calculate distance between coordinates
- Configurable search radius (default: 5km)
- Returns drivers sorted by distance
- Only searches AVAILABLE/ONLINE drivers

#### Logging
All operations are logged with:
- Trip ID
- Driver ID
- Attempt number (for retries)
- Success/failure status
- Error details

### Task #42: Driver Response Handling (NEW in v0.2.0)

#### Response Processing
- Validates driver and trip existence
- Checks for duplicate responses (idempotency)
- Verifies trip is not already assigned
- Updates driver status (ON_TRIP for accept, AVAILABLE for reject)

#### Accept Flow
1. Receive `driver.cmd.trip_accept` event
2. Validate response
3. Update trip status to "assigned"
4. Update driver status to "ON_TRIP"
5. Publish `trip.event.driver_assigned` to Trip Service

#### Reject Flow (MVP)
1. Receive `driver.cmd.trip_reject` event
2. Validate response
3. Record rejection
4. Update driver status back to "AVAILABLE"
5. Log rejection (follow-up logic not yet implemented)

#### Idempotency
- Tracks all driver responses in memory
- Prevents duplicate processing of same response
- Gracefully handles repeated accept/reject events

#### Storage Structure
```python
trip_requests = {
    "trip_123": {
        "status": "pending|assigned",
        "assigned_driver_id": "driver_001",  # if assigned
        "notified_drivers": ["driver_001", "driver_002"],
        "responses": {
            "driver_001": "accept",
            "driver_002": "reject"
        },
        "created_at": "2026-01-17T19:00:00Z",
        "assigned_at": "2026-01-17T19:05:00Z"
    }
}
```

## Integration

### With Trip Service
- Consumes `trip.event.created` events
- Publishes `trip.event.driver_assigned` events *(NEW)*
- Event format matches Trip Service schema

### With Client Gateway
- Sends HTTP POST to `/api/v1/notifications/driver/{driver_id}`
- Receives `driver.cmd.trip_accept/reject` events via RabbitMQ *(NEW)*
- Requires Client Gateway to forward notifications to Telegram Bot

### With Database (Future)
- Currently uses in-memory storage for development
- PostgreSQL integration planned for persistent trip request tracking

## Version History

### v0.2.0 (2026-01-17) - Task #42
- ✨ Added driver response handling (accept/reject)
- ✨ Added `trip.event.driver_assigned` event publishing
- ✨ Added idempotency for driver responses
- ✨ Added trip request tracking and monitoring endpoints
- ✨ Added `DriverResponseConsumer` and `DriverResponseService`
- ✨ Added `RabbitMQPublisher` for event publishing
- 🔧 Updated `TripEventsConsumer` to track trip requests
- 📝 Added comprehensive logging for all response operations

### v0.1.0 (Previous) - Task #41
- Initial release with trip request notifications
- Driver management CRUD operations
- Nearby driver search with Haversine distance
- RabbitMQ integration for trip.event.created
- Retry mechanism for failed notifications

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

Internal project - UA-4697-DevOps team
