import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import UUID
from typing import Optional
from fastapi import FastAPI, HTTPException, status, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

# Internal Imports
from src.database import get_db
from src.driver_models import Driver, BotUser
from src.services.driver_repository import DriverRepository
from src.services.bot_user_repository import BotUserRepository
from src.schemas.driver_schemas import DriverCreate, DriverResponse, LocationUpdate
from src.schemas.bot_user_schemas import (
    BotUserCreate,
    BotUserUpdate,
    BotUserResponse,
    BotUserDriverRegistration
)
from src.config import settings
from src.schemas.trip_request import TripRequestNotification
from src.services.driver_notification_service import DriverNotificationService
from src.clients.gateway_client import ClientGatewayClient
from src.clients.sqs_publisher import SQSPublisher
from src.services.driver_response_service import DriverResponseService

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# In-memory storage (Temporary solution before DB migration)
drivers = {}
trip_requests = {}

# Global services references
gateway_client = None
notification_service = None
sqs_publisher = None
response_service = None

# Background Task references for graceful shutdown
trip_sqs_consumer_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI application startup and shutdown"""
    global gateway_client, notification_service, sqs_publisher, response_service
    global trip_sqs_consumer_task

    # --- STARTUP PHASE ---
    logger.info("Starting Driver Service (SQS Unified Mode)...")

    # Attach storage to app state for access in endpoint dependencies
    app.state.drivers_storage = drivers
    app.state.trip_requests_storage = trip_requests
    app.state.response_service = None  # Initialize as None for safety check

    logger.info(f"Lifespan: Initialized trip_requests_storage (id={id(trip_requests)})")

    # Initialize Client Gateway (Telegram Bot API)
    gateway_client = ClientGatewayClient(
        base_url=settings.CLIENT_GATEWAY_URL,
        timeout=settings.GATEWAY_TIMEOUT
    )

    # Initialize internal notification logic
    notification_service = DriverNotificationService(
        gateway_client=gateway_client,
        drivers_storage=drivers,
        max_retries=settings.MAX_RETRY_ATTEMPTS
    )

    # 1. Initialize AWS SQS Integration (Publisher)
    try:
        sqs_publisher = SQSPublisher()
        logger.info("SQS Publisher successfully initialized")

        # Initialize Driver Response Service using the SQS Publisher
        response_service = DriverResponseService(
            publisher=sqs_publisher,
            drivers_storage=drivers,
            trip_requests_storage=trip_requests
        )
        app.state.response_service = response_service
        logger.info("Driver Response Service initialized with SQS")

    except Exception as e:
        logger.error(f"CRITICAL ERROR: Failed to initialize SQS Publisher: {e}")
        # FAIL FAST: The service is useless without SQS connectivity
        raise SystemExit(1)

    # 2. Start Background SQS Consumer
    logger.info("Initializing Background SQS Consumers...")

    if settings.SQS_TRIP_CREATED_URL:
        try:
            from src.consumers.trip_sqs_consumer import TripSQSConsumer
            logger.info(f"Starting TripSQSConsumer for queue: {settings.SQS_TRIP_CREATED_URL}")

            trip_sqs_consumer = TripSQSConsumer(
                notification_service=notification_service,
                trip_requests_storage=trip_requests
            )

            # SQS consumer is native async, managed directly by the event loop
            trip_sqs_consumer_task = asyncio.create_task(trip_sqs_consumer.start())
            logger.info("Trip SQS Consumer background task successfully started")
        except Exception as e:
            logger.error(f"Failed to start SQS Trip Consumer: {e}")
    else:
        logger.warning("SQS_TRIP_CREATED_URL not found. Driver service will not receive new trip requests.")

    logger.info("Driver Service startup phase finished")

    yield

    # --- SHUTDOWN PHASE ---
    logger.info("Shutting down Driver Service...")

    # [FIXED] Simplified shutdown: RabbitMQ logic removed
    if trip_sqs_consumer_task:
        trip_sqs_consumer_task.cancel()
        try:
            await trip_sqs_consumer_task
            logger.info("Background SQS task shut down.")
        except asyncio.CancelledError:
            pass

    if gateway_client:
        await gateway_client.close()
        logger.info("Gateway client connection closed.")

    logger.info("Driver Service stopped gracefully")

app = FastAPI(
  title="Driver Service API",
  description="""
      Driver Service for ride-hailing platform.
      """,
  version="1.0.0",

  docs_url="/docs" if settings.DEBUG else None,
  redoc_url="/redoc" if settings.DEBUG else None,
  openapi_url="/openapi.json" if settings.DEBUG else None,

  lifespan=lifespan
)

# Helper for dependency injection
def get_notification_service():
    """Return the global notification service instance"""
    return notification_service

# ========== DEBUGGING & STATUS ENDPOINTS ==========

@app.get("/drivers/status/online", response_model=list[DriverResponse], tags=["Debugging"])
async def get_online_drivers(db: AsyncSession = Depends(get_db)):
    """
    Get list of all active drivers (is_active=True).
    Used for debugging or checking availability before sending Trip Request.
    """
    repo = DriverRepository(db)
    drivers_list = await repo.list_all()

    # Filter by is_active field
    online_drivers = [d for d in drivers_list if getattr(d, 'is_active', False)]

    logger.info(f"🔍 Debug: Found {len(online_drivers)} online drivers")
    return online_drivers

# ========== CRUD ENDPOINTS (Database) ==========

@app.post("/drivers", response_model=DriverResponse, status_code=status.HTTP_201_CREATED, tags=["Drivers"])
async def register_driver(driver_in: DriverCreate, db: AsyncSession = Depends(get_db)):
    """Register new driver (or return existing if phone number matches)"""
    repo = DriverRepository(db)

    # Check if driver with this phone_number already exists
    existing_driver = await repo.get_by_phone_number(driver_in.phone_number)
    if existing_driver:
        logger.info(f"Driver with phone {driver_in.phone_number} already exists (ID: {existing_driver.id}), returning existing driver")
        driver = existing_driver
    else:
        # Create new driver
        driver = await repo.create(**driver_in.model_dump())
        logger.info(f"New driver {driver.id} created with phone {driver_in.phone_number}")

    # Sync with in-memory storage for notification service and SQS consumer context
    drivers_storage = app.state.drivers_storage
    drivers_storage[str(driver.id)] = {
        "id": str(driver.id),
        "name": f"{driver.first_name} {driver.last_name}",
        "status": "ONLINE" if driver.is_active else "OFFLINE",
        "latitude": 50.4501,  # Default Kyiv coordinates
        "longitude": 30.5234
    }
    logger.info(f"Driver {driver.id} synced to in-memory storage")

    return driver

@app.get("/drivers", response_model=list[DriverResponse], tags=["Drivers"])
async def list_drivers(db: AsyncSession = Depends(get_db)):
    """List all drivers"""
    repo = DriverRepository(db)
    return await repo.list_all()

@app.get("/drivers/{driver_id}", response_model=DriverResponse, tags=["Drivers"])
async def get_driver(driver_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = DriverRepository(db)
    driver = await repo.get_by_id(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver

@app.patch("/drivers/{driver_id}/status", response_model=DriverResponse, tags=["Drivers"])
async def update_driver_status(driver_id: UUID, is_active: bool, db: AsyncSession = Depends(get_db)):
    """Update driver activity status and sync with in-memory storage"""
    repo = DriverRepository(db)
    updated = await repo.update(driver_id, is_active=is_active)
    if not updated:
        raise HTTPException(status_code=404, detail="Driver not found")

    # Sync with in-memory storage for the SQS-based notification service
    drivers_storage = app.state.drivers_storage
    driver_key = str(driver_id)
    if driver_key in drivers_storage:
        drivers_storage[driver_key]["status"] = "ONLINE" if is_active else "OFFLINE"
        logger.info(f"Driver {driver_id} status updated to {'ONLINE' if is_active else 'OFFLINE'} in in-memory storage")
    else:
        # Create entry if it doesn't exist (fallback synchronization)
        drivers_storage[driver_key] = {
            "id": driver_key,
            "name": f"{updated.first_name} {updated.last_name}",
            "status": "ONLINE" if is_active else "OFFLINE",
            "latitude": 50.4501, # Default coordinates for discovery radius
            "longitude": 30.5234
        }
        logger.info(f"Driver {driver_id} created in in-memory storage with status {'ONLINE' if is_active else 'OFFLINE'}")

    return updated


@app.post("/drivers/{driver_id}/location", tags=["Drivers"], summary="Update driver GPS coordinates")
async def update_driver_location(driver_id: UUID, location: LocationUpdate):
    drivers_storage = app.state.drivers_storage
    driver_key = str(driver_id)

    if driver_key not in drivers_storage:
        raise HTTPException(status_code=404, detail="Driver not found in memory storage")

    drivers_storage[driver_key]["latitude"] = location.lat
    drivers_storage[driver_key]["longitude"] = location.lng

    logger.info(f"Driver {driver_id} location updated to {location.lat}, {location.lng}")
    return {"status": "success", "driver_id": driver_id}


@app.get("/drivers/{driver_id}/inspection", tags=["Drivers"], summary="Check vehicle inspection status")
async def get_driver_inspection(driver_id: UUID):
    """
    Returns the vehicle verification and documents status for the driver.
    Ensures the driver exists in memory before returning status.
    """
    drivers_storage = app.state.drivers_storage
    driver_key = str(driver_id)

    if driver_key not in drivers_storage:
        raise HTTPException(status_code=404, detail="Driver not found in memory storage")

    return {
        "driver_id": driver_id,
        "status": "approved",
        "last_inspection_date": "2026-02-15",
        "inspection_type": "annual",
        "is_mock_data": True
    }


# ========== BOT USERS MANAGEMENT ==========

@app.post("/api/bot-users", response_model=BotUserResponse, tags=["Bot Users"])
async def create_or_get_bot_user(
    user_data: BotUserCreate,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Get or create bot user by telegram_chat_id.
    Returns HTTP 201 if created, HTTP 200 if retrieved existing.
    """
    repo = BotUserRepository(db)
    bot_user, created = await repo.get_or_create(
        chat_id=user_data.telegram_chat_id,
        defaults={'current_role': user_data.current_role}
    )

    if created:
        response.status_code = status.HTTP_201_CREATED
        logger.info(f"Created new bot user: chat_id={bot_user.telegram_chat_id}")
    else:
        response.status_code = status.HTTP_200_OK
        logger.info(f"Retrieved existing bot user: chat_id={bot_user.telegram_chat_id}")

    return bot_user


@app.get("/api/bot-users/{chat_id}", response_model=BotUserResponse, tags=["Bot Users"])
async def get_bot_user(chat_id: int, db: AsyncSession = Depends(get_db)):
    """Get bot user profile by telegram chat ID"""
    repo = BotUserRepository(db)
    bot_user = await repo.get_by_chat_id(chat_id)
    if not bot_user:
        raise HTTPException(status_code=404, detail="Bot user not found")
    return bot_user


@app.patch("/api/bot-users/{chat_id}", response_model=BotUserResponse, tags=["Bot Users"])
async def update_bot_user(chat_id: int, updates: BotUserUpdate, db: AsyncSession = Depends(get_db)):
    """Update bot user fields (role, status, etc.)"""
    repo = BotUserRepository(db)

    # Filter out None values to avoid overwriting existing data with nulls
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    bot_user = await repo.update(chat_id, **update_data)
    if not bot_user:
        raise HTTPException(status_code=404, detail="Bot user not found")

    return bot_user


@app.post("/api/bot-users/register-driver", response_model=BotUserResponse, tags=["Bot Users"])
async def register_bot_user_as_driver(
    registration: BotUserDriverRegistration,
    db: AsyncSession = Depends(get_db)
):
    """
    Register bot user as driver.
    Creates Driver record and updates BotUser with driver info.
    All operations are performed within a single database transaction.
    """
    bot_user_repo = BotUserRepository(db)
    driver_repo = DriverRepository(db)

    # Get or create bot user profile
    bot_user, created = await bot_user_repo.get_or_create(registration.telegram_chat_id)

    # Idempotency check: Already registered
    if bot_user.driver_id:
        logger.info(f"Bot user {registration.telegram_chat_id} already registered as driver")
        return bot_user

    # Name normalization
    name_parts = registration.driver_name.strip().split(maxsplit=1)
    first_name = name_parts[0] if name_parts else "Driver"
    last_name = name_parts[1] if len(name_parts) > 1 else str(registration.telegram_chat_id)

    # Generate phone number from chat_id for unique identification
    chat_id_str = str(registration.telegram_chat_id)
    phone_suffix = chat_id_str[-10:] if len(chat_id_str) >= 10 else chat_id_str.zfill(10)
    phone_number = f"+{phone_suffix}"

    # Check for existing driver profile
    existing_driver = await driver_repo.get_by_phone_number(phone_number)

    try:
        if existing_driver:
            driver = existing_driver
            driver_id = driver.id
            logger.info(f"Linking existing driver profile {driver_id} to bot user {registration.telegram_chat_id}")
        else:
            # Create Driver record
            driver = Driver(
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                is_active=True
            )
            db.add(driver)
            await db.flush()  # Flush to get driver.id
            driver_id = driver.id
            logger.info(f"Created new driver profile: {driver_id}")

        # Atomic update of BotUser
        stmt = (
            update(BotUser)
            .where(BotUser.telegram_chat_id == registration.telegram_chat_id)
            .values(
                driver_id=driver_id,
                driver_name=registration.driver_name,
                car_description=registration.car_description,
                current_role='driver'
            )
            .returning(BotUser)
        )
        result = await db.execute(stmt)
        bot_user = result.scalar_one_or_none()

        if not bot_user:
            raise HTTPException(status_code=404, detail="Failed to update bot user with driver info")

        # Commit transaction
        await db.commit()
        await db.refresh(bot_user)

        # Sync with in-memory storage (Crucial for SQS Discovery)
        drivers_storage = app.state.drivers_storage
        drivers_storage[str(driver_id)] = {
            "id": str(driver_id),
            "name": registration.driver_name,
            "status": "OFFLINE",  # Default status after registration
            "latitude": 50.4501,  # Default Kyiv coordinates
            "longitude": 30.5234
        }

        logger.info(f"Bot user {registration.telegram_chat_id} successfully linked to driver {driver_id}")
        return bot_user

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Registration failure for chat_id={registration.telegram_chat_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Driver registration failed: {str(e)}")

@app.patch("/api/bot-users/{chat_id}/role", response_model=BotUserResponse, tags=["Bot Users"])
async def change_bot_user_role(chat_id: int, role: str, db: AsyncSession = Depends(get_db)):
    """
    Change user's current role (driver/passenger).
    Preserves all data - user can switch between roles freely.
    """
    if role not in ['driver', 'passenger']:
        raise HTTPException(status_code=400, detail="Role must be 'driver' or 'passenger'")

    repo = BotUserRepository(db)
    bot_user = await repo.update_role(chat_id, role)

    if not bot_user:
        raise HTTPException(status_code=404, detail="Bot user not found")

    logger.info(f"Bot user {chat_id} changed role to {role}")
    return bot_user


@app.patch("/api/bot-users/{chat_id}/driver-status", response_model=BotUserResponse, tags=["Bot Users"])
async def update_bot_user_driver_status(
    chat_id: int,
    is_online: bool,
    db: AsyncSession = Depends(get_db)
):
    """Update driver's online/offline status and sync with SQS search context"""
    repo = BotUserRepository(db)
    bot_user = await repo.get_by_chat_id(chat_id)

    if not bot_user or not bot_user.driver_id:
        raise HTTPException(status_code=404, detail="Bot user not registered as driver")

    new_status = 'online' if is_online else 'offline'
    bot_user = await repo.update_driver_status(chat_id, new_status)

    # Sync with in-memory storage (Critical for SQS Radius Search)
    drivers_storage = app.state.drivers_storage
    driver_key = str(bot_user.driver_id)

    if driver_key in drivers_storage:
        drivers_storage[driver_key]["status"] = "ONLINE" if is_online else "OFFLINE"
    else:
        # Create a basic entry if missing from memory to ensure consistency
        drivers_storage[driver_key] = {
            "id": driver_key,
            "name": bot_user.driver_name or f"Driver {driver_key}",
            "status": "ONLINE" if is_online else "OFFLINE",
            "latitude": 50.4501,  # Default to Kyiv center
            "longitude": 30.5234
        }

    logger.info(f"Bot user {chat_id} driver status changed to {new_status} (SQS Discovery Sync)")
    return bot_user


@app.patch("/api/bot-users/{chat_id}/active-trip", response_model=BotUserResponse, tags=["Bot Users"])
async def set_bot_user_active_trip(
    chat_id: int,
    trip_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Set or clear active trip for driver (Database state only)"""
    repo = BotUserRepository(db)
    bot_user = await repo.get_by_chat_id(chat_id)

    if not bot_user or not bot_user.driver_id:
        raise HTTPException(status_code=404, detail="Bot user not registered as driver")

    bot_user = await repo.set_active_trip(chat_id, trip_id)

    if trip_id:
        logger.info(f"Bot user {chat_id} started trip {trip_id}")
    else:
        logger.info(f"Bot user {chat_id} cleared active trip")

    return bot_user


# ========== TASK #41: TRIP REQUESTS ==========

@app.post("/api/v1/trip-requests/send", status_code=status.HTTP_202_ACCEPTED, tags=["Trip Requests"])
async def send_trip_request(
    notification: TripRequestNotification,
    service: DriverNotificationService = Depends(get_notification_service)
):
    """
    Send trip request to driver (Internal Gateway Trigger).
    Standardized for SQS-only unified event flow.
    """
    success = await service.send_trip_request_to_driver(
        driver_id=notification.driver_id,
        notification=notification
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Driver unavailable or notification failed"
        )

    # Track trip request in storage for upcoming SQS Accept/Reject processing
    trip_requests_storage = app.state.trip_requests_storage

    if notification.trip_id not in trip_requests_storage:
        trip_requests_storage[notification.trip_id] = {
            "status": "pending",
            "notified_drivers": [notification.driver_id],
            "responses": {},
            "created_at": notification.created_at.isoformat(),
            "pickup": notification.pickup.model_dump(),
            "dropoff": notification.dropoff.model_dump()
        }
    else:
        # Support multiple driver notifications for the same trip (Unified Context)
        trip_record = trip_requests_storage[notification.trip_id]
        if notification.driver_id not in trip_record.get("notified_drivers", []):
            trip_record.setdefault("notified_drivers", []).append(notification.driver_id)

    logger.info(f"Notification recorded for Trip {notification.trip_id} -> Driver {notification.driver_id}")

    return {
        "message": "Trip request sent successfully",
        "trip_id": notification.trip_id,
        "driver_id": notification.driver_id
    }

# ========== MONITORING & TRIP MANAGEMENT ==========

@app.get("/api/v1/trip-requests", tags=["Monitoring"])
def list_trip_requests():
    """
    List all tracked trip requests in memory.
    Used to verify the state managed by the TripSQSConsumer.
    """
    trip_requests_storage = app.state.trip_requests_storage
    logger.info(f"list_trip_requests called: count={len(trip_requests_storage)}")
    return {
        "trip_requests": trip_requests_storage,
        "count": len(trip_requests_storage)
    }


@app.get("/api/v1/trip-requests/{trip_id}", tags=["Monitoring"])
def get_trip_request(trip_id: str):
    """Get details of a specific trip tracked in the unified SQS state."""
    trip_requests_storage = app.state.trip_requests_storage
    trip_data = trip_requests_storage.get(trip_id)
    if not trip_data:
        raise HTTPException(status_code=404, detail="Trip request context not found")

    return {
        "trip_id": trip_id,
        **trip_data
    }


@app.get("/drivers/{driver_id}/trips", tags=["Driver Operations"])
async def get_driver_trips(driver_id: str):
    """
    List available PENDING trips for the Telegram bot "My Orders" view.
    Filtered from the shared SQS memory storage.
    """
    try:
        drivers_storage = app.state.drivers_storage
        trip_requests_storage = app.state.trip_requests_storage
    except AttributeError:
        # Fallback for local unit testing environments
        drivers_storage = drivers
        trip_requests_storage = trip_requests

    if driver_id not in drivers_storage:
        raise HTTPException(status_code=404, detail="Driver identity not found in memory")

    available_trips = []
    for trip_id, trip_data in trip_requests_storage.items():
        # Only show trips that are PENDING and not yet assigned to any driver
        if trip_data.get("status") == "pending":
            pickup = trip_data.get("pickup", {})
            dropoff = trip_data.get("dropoff", {})

            available_trips.append({
                "trip_id": trip_id,
                "pickup_address": pickup.get("address", "Unknown Location"),
                "dropoff_address": dropoff.get("address", "Unknown Location"),
                "status": "PENDING",
                "created_at": trip_data.get("created_at", "")
            })

    return {
        "trips": available_trips,
        "count": len(available_trips)
    }


@app.post("/drivers/{driver_id}/trips/{trip_id}/accept", tags=["Driver Operations"])
async def accept_trip(driver_id: str, trip_id: str, db: AsyncSession = Depends(get_db)):
    """
    Finalize trip acceptance and notify Trip Service via AWS SQS FIFO.
    Triggered by the Telegram bot "Accept" button.
    """
    if not app.state.response_service:
        raise HTTPException(status_code=503, detail="SQS Response service not initialized")

    drivers_storage = app.state.drivers_storage
    trip_requests_storage = app.state.trip_requests_storage

    # 1. Verify Driver exists and is synchronized
    from uuid import UUID
    try:
        driver_uuid = UUID(driver_id)
        repo = DriverRepository(db)
        driver = await repo.get_by_id(driver_uuid)

        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found in DB")

        if driver_id not in drivers_storage:
            drivers_storage[driver_id] = {
                "id": driver_id,
                "name": f"{driver.first_name} {driver.last_name}",
                "status": "ONLINE" if driver.is_active else "OFFLINE",
                "latitude": 50.4501,
                "longitude": 30.5234
            }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid driver UUID format")

    # 2. Verify Trip exists in the SQS consumer context
    if trip_id not in trip_requests_storage:
        raise HTTPException(status_code=404, detail="Trip request not found in SQS memory context")

    # 3. Process Acceptance via SQSPublisher
    from datetime import datetime, timezone
    success = await app.state.response_service.handle_driver_accept(
        driver_id=driver_id,
        trip_id=trip_id,
        timestamp=datetime.now(timezone.utc)
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to publish acceptance event to SQS FIFO")

    trip_data = trip_requests_storage.get(trip_id, {})
    return {
        "message": "Trip successfully accepted via SQS FIFO",
        "trip_id": trip_id,
        "driver_id": driver_id,
        "pickup_address": trip_data.get("pickup", {}).get("address", "N/A"),
        "dropoff_address": trip_data.get("dropoff", {}).get("address", "N/A")
    }


@app.post("/drivers/{driver_id}/trips/{trip_id}/reject", tags=["Driver Operations"])
async def reject_trip(driver_id: str, trip_id: str, db: AsyncSession = Depends(get_db)):
    """
    Driver rejects trip request.
    Triggers rejection logic via SQS and updates local state.
    """
    from uuid import UUID
    from datetime import datetime, timezone

    # Access unified SQS response service
    if not app.state.response_service:
        raise HTTPException(status_code=503, detail="SQS Response service not initialized")

    drivers_storage = app.state.drivers_storage
    trip_requests_storage = app.state.trip_requests_storage

    # 1. Verify and Sync Driver State
    try:
        driver_uuid = UUID(driver_id)
        repo = DriverRepository(db)
        driver = await repo.get_by_id(driver_uuid)

        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found in database")

        if driver_id not in drivers_storage:
            logger.warning(f"Syncing driver {driver_id} to memory storage during rejection")
            drivers_storage[driver_id] = {
                "id": driver_id,
                "name": f"{driver.first_name} {driver.last_name}",
                "status": "ONLINE" if driver.is_active else "OFFLINE",
                "latitude": 50.4501,
                "longitude": 30.5234
            }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid driver UUID format")

    # 2. Verify Trip Context
    if trip_id not in trip_requests_storage:
        raise HTTPException(status_code=404, detail="Trip request context not found")

    # 3. Publish Rejection to SQS
    success = await app.state.response_service.handle_driver_reject(
        driver_id=driver_id,
        trip_id=trip_id,
        timestamp=datetime.now(timezone.utc)
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to publish rejection event to SQS")

    return {
        "message": "Trip rejected successfully via SQS",
        "trip_id": trip_id,
        "driver_id": driver_id
    }


@app.post("/drivers/{driver_id}/trips/{trip_id}/complete", tags=["Driver Operations"])
async def complete_trip(driver_id: str, trip_id: str, db: AsyncSession = Depends(get_db)):
    """
    Driver completes trip.
    Publishes completion event to Go trip-service via SQS FIFO.
    """
    from uuid import UUID
    from datetime import datetime, timezone

    drivers_storage = app.state.drivers_storage
    trip_requests_storage = app.state.trip_requests_storage

    # 1. Verify Driver and sync memory
    try:
        driver_uuid = UUID(driver_id)
        repo = DriverRepository(db)
        driver = await repo.get_by_id(driver_uuid)

        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found in database")

        if driver_id not in drivers_storage:
            logger.info(f"Syncing driver {driver_id} from DB to memory for completion flow")
            drivers_storage[driver_id] = {
                "id": driver_id,
                "name": f"{driver.first_name} {driver.last_name}",
                "status": "ONLINE" if driver.is_active else "OFFLINE",
                "latitude": 50.4501,
                "longitude": 30.5234
            }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid driver ID format")

    # 2. Safety check for Response Service
    if not app.state.response_service:
        raise HTTPException(status_code=503, detail="SQS Response service not initialized")

    # 3. Process completion via DriverResponseService
    # This publishes the 'trip.completed' event to AWS SQS
    success = await app.state.response_service.handle_trip_completion(
        driver_id=driver_id,
        trip_id=trip_id,
        timestamp=datetime.now(timezone.utc)
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to publish SQS completion event")

    return {
        "message": "Trip completed; event published to SQS FIFO",
        "trip_id": trip_id,
        "driver_id": driver_id,
        "status": "completed"
    }


@app.get("/health", tags=["Monitoring"])
def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    In production, this should also check DB and SQS connectivity.
    """
    return {"status": "healthy"}


@app.get("/", tags=["Monitoring"])
def root():
    """
    Root endpoint with dynamic service and cloud-native feature status.
    Reflects the finalized SQS FIFO architecture.
    """
    return {
        "service": "Driver Service",
        "version": "1.0.0-sqs",
        "status": "running",
        "architecture": "AWS SQS FIFO",
        "features": {
            "driver_management": True,
            "trip_requests": True,
            "driver_responses": True,
            # Dynamically check if SQS components were initialized during lifespan
            "sqs_enabled": app.state.response_service is not None,
            # Explicitly False as part of the RabbitMQ decommission
            "legacy_rabbitmq_enabled": False
        }
    }
