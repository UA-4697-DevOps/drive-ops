# AI Context: drive-ops

## 1. Project Overview & Architecture
**Project:** drive-ops (Ride-Sharing Platform)
**Architecture:** Microservices
**Database Pattern:** Database-per-service (No shared tables).
**Communication Channels:**
* **Synchronous (HTTP/REST):**
    * `TG User` <-> `Client Gateway` (Telegram API)
    * `Client Gateway` -> `Trip Service` (Create Order / Poll Status)
    * `Client Gateway` -> `Driver Service` (Accept Order)
    * `Driver Service` -> `Client Gateway` (Webhook: Notify Driver)
* **Asynchronous (RabbitMQ):**
    * `Trip Service` -> `Driver Service` (Topic: `trip.created`)
    * `Driver Service` -> `Trip Service` (Topic: `trip.driver_assigned`)

### System Data Flow (Source of Truth)
This diagram defines the canonical flow for Ride Creation and Assignment.
```mermaid
sequenceDiagram
    autonumber
    participant P as Passenger (TG User)
    participant D as Driver (TG User)
    participant CG as Client Gateway (TG Bot)
    participant TS as Trip Service
    participant MB as RabbitMQ
    participant DS as Driver Service

    Note over P, TS: Phase 1: Order Creation
    P->>CG: Command: /order (Origin, Destination)
    CG->>TS: POST /internal/trips
    TS->>TS: Save Trip (Status: PENDING)
    TS-->>CG: 201 Created (TripID)
    CG-->>P: 201 Created (TripID)

    Note over TS, DS: Phase 2: Driver Discovery (Bridge)
    TS->>MB: Publish: trip.event.created
    MB-->>DS: Consume: trip.event.created
    DS->>DS: Search drivers in driver_db
    DS->>CG: POST /notify-driver (Webhook)
    CG->>D: New Trip Request available!

    Note over D, TS: Phase 3: Driver Acceptance
    D->>CG: Click: [Accept]
    CG->>DS: POST /internal/accept-trip
    DS-->>CG: 200 OK
    CG-->>D: 200 OK
    
    DS->>MB: Publish: trip.event.driver_assigned
    MB-->>TS: Consume: trip.event.driver_assigned
    TS->>TS: Update trip_db (Status: ACTIVE, DriverID)

    Note over P, TS: Phase 4: Status Polling (User Initiated)
    P->>CG: Click: [Check Status] (or /status)
    CG->>TS: GET /internal/trips/{id}
    TS-->>CG: Trip DTO (Status: ACTIVE, Driver Info)
    CG-->>P: Trip description
```
