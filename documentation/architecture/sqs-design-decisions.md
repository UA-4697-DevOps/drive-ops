# SQS Migration - Design Decisions

---

## Subtask 1: Queue Definition

### Queues for MVP

| Queue Name | Producer | Consumer | Purpose |
|------------|----------|----------|---------|
| `trip-created` | Trip Service | Driver Service | New trip requests |
| `driver-assigned` | Driver Service | Trip Service | Driver acceptance |
| `trip-completed` | Driver Service | Trip Service | Trip completion |

**Note:** Commands (`driver_cmd_*`) are NOT needed - HTTP endpoints are used instead.

---

## Subtask 2: DLQ Configuration

### Dead Letter Queue (DLQ) Settings

- **Max Receive Count:** 3 attempts
- **DLQ Retention:** 14 days (1,209,600 seconds)
- **Naming:** `{queue-name}-dlq-{env}.fifo`

**Rationale:**
- 3 retries balance resilience vs. cost
- 14 days allows manual investigation and reprocessing

---

## Subtask 3: Queue Type Decision

### FIFO vs Standard

**Decision:** FIFO queues

**Rationale:**
- Event ordering is critical per trip (created → assigned → completed)
- Message Group ID: `trip-{tripId}` ensures per-trip ordering
- Content-based deduplication prevents duplicate events

---

## Subtask 4: Message Envelope

### Envelope Structure
```json
{
  "version": "1.0",
  "messageId": "uuid-v4",
  "timestamp": "2026-01-27T14:20:00Z",
  "correlationId": "trip-{tripId}",
  "eventType": "trip.created | driver.assigned | trip.completed",
  "source": "trip-service | driver-service",
  "payload": {}
}
```

### Event Payloads

#### trip.created
```json
{
  "version": "1.0",
  "messageId": "a1b2c3d4-...",
  "timestamp": "2026-01-27T14:20:00Z",
  "correlationId": "trip-550e8400-...",
  "eventType": "trip.created",
  "source": "trip-service",
  "payload": {
    "tripId": "550e8400-...",
    "passengerId": "passenger-123",
    "origin": {
      "latitude": 49.8397,
      "longitude": 24.0297
    },
    "destination": {
      "latitude": 49.8429,
      "longitude": 24.0314
    },
    "status": "PENDING",
    "createdAt": "2026-01-27T14:20:00Z"
  }
}
```

#### driver.assigned
```json
{
  "version": "1.0",
  "messageId": "b2c3d4e5-...",
  "timestamp": "2026-01-27T14:21:30Z",
  "correlationId": "trip-550e8400-...",
  "eventType": "driver.assigned",
  "source": "driver-service",
  "payload": {
    "tripId": "550e8400-...",
    "driverId": "driver-456",
    "driverName": "John Doe",
    "vehicleInfo": {
      "make": "Toyota",
      "model": "Prius",
      "licensePlate": "ABC-1234"
    },
    "assignedAt": "2026-01-27T14:21:30Z"
  }
}
```

#### trip.completed
```json
{
  "version": "1.0",
  "messageId": "c3d4e5f6-...",
  "timestamp": "2026-01-27T15:00:00Z",
  "correlationId": "trip-550e8400-...",
  "eventType": "trip.completed",
  "source": "driver-service",
  "payload": {
    "tripId": "550e8400-...",
    "driverId": "driver-456",
    "completedAt": "2026-01-27T15:00:00Z",
    "status": "COMPLETED"
  }
}
```
