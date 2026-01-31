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
from src.schemas.driver_schemas import DriverCreate, DriverResponse
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

# Consumers references for graceful shutdown
trip_events_consumer = None
driver_responses_consumer = None
trip_events_consumer_task = None
driver_responses_consumer_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI application startup and shutdown"""
    global gateway_client, notification_service, sqs_publisher, response_service
    global trip_events_consumer, driver_responses_consumer
    global trip_events_consumer_task, driver_responses_consumer_task

    # --- STARTUP PHASE ---
    logger.info("Starting Driver Service...")

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

    # 1. Initialize AWS SQS Integration
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
        logger.error(f"CRITICAL ERROR: Failed to initialize SQS components: {e}")
        # We do not stop the app here to allow health checks, but services will be degraded.

    # 2. Start Background Message Queue Consumers
    if settings.RABBITMQ_HOST:
        try:
            # Trip Events Consumer: Handles incoming trip creation notifications
            from consumers.trip_events_consumer import TripEventsConsumer
            logger.info("Creating TripEventsConsumer (RabbitMQ)...")
            trip_events_consumer = TripEventsConsumer(
                rabbitmq_host=settings.RABBITMQ_HOST,
                rabbitmq_port=settings.RABBITMQ_PORT,
                rabbitmq_user=settings.RABBITMQ_USER,
                rabbitmq_pass=settings.RABBITMQ_PASS,
                queue_name=settings.TRIP_EVENTS_QUEUE,
                notification_service=notification_service,
                trip_requests_storage=trip_requests
            )
            trip_events_consumer_task = asyncio.create_task(
                asyncio.to_thread(trip_events_consumer.start_consuming)
            )
            logger.info("Trip Events Consumer background task started")

            # Driver Responses Consumer: Handles accept/reject commands from drivers
            # [FIXED] Guard check: Do not start if response_service failed to initialize
            if response_service:
                from consumers.driver_response_consumer import DriverResponseConsumer
                driver_responses_consumer = DriverResponseConsumer(
                    rabbitmq_host=settings.RABBITMQ_HOST,
                    rabbitmq_port=settings.RABBITMQ_PORT,
                    rabbitmq_user=settings.RABBITMQ_USER,
                    rabbitmq_pass=settings.RABBITMQ_PASS,
                    queue_name=settings.DRIVER_RESPONSES_QUEUE,
                    response_service=response_service
                )
                driver_responses_consumer_task = asyncio.create_task(
                    asyncio.to_thread(driver_responses_consumer.start_consuming)
                )
                logger.info("Driver Responses Consumer background task started")
            else:
                logger.warning("SKIPPED: DriverResponseConsumer not started because response_service is None")

        except Exception as e:
            logger.error(f"Failed to start RabbitMQ consumers: {e}")

    logger.info("Driver Service startup phase finished")

    yield

    # --- SHUTDOWN PHASE ---
    logger.info("Shutting down Driver Service...")

    if trip_events_consumer_task:
        if trip_events_consumer:
            trip_events_consumer.stop()
        trip_events_consumer_task.cancel()
        try:
            await trip_events_consumer_task
        except asyncio.CancelledError:
            pass

    if driver_responses_consumer_task:
        if driver_responses_consumer:
            driver_responses_consumer.stop()
        driver_responses_consumer_task.cancel()
        try:
            await driver_responses_consumer_task
        except asyncio.CancelledError:
            pass

    if gateway_client:
        await gateway_client.close()

    logger.info("Driver Service stopped gracefully")

app = FastAPI(
    title="DriverService",
    version="0.1.0",
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
    drivers = await repo.list_all()
    # Filter by is_active field
    online_drivers = [d for d in drivers if getattr(d, 'is_active', False)]
    
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
    """Update driver activity status"""
    repo = DriverRepository(db)
    updated = await repo.update(driver_id, is_active=is_active)
    if not updated:
        raise HTTPException(status_code=404, detail="Driver not found")

    # Sync with in-memory storage
    drivers_storage = app.state.drivers_storage
    driver_key = str(driver_id)
    if driver_key in drivers_storage:
        drivers_storage[driver_key]["status"] = "ONLINE" if is_active else "OFFLINE"
        logger.info(f"Driver {driver_id} status updated to {'ONLINE' if is_active else 'OFFLINE'} in in-memory storage")
    else:
        # Create entry if it doesn't exist (fallback)
        drivers_storage[driver_key] = {
            "id": driver_key,
            "name": f"{updated.first_name} {updated.last_name}",
            "status": "ONLINE" if is_active else "OFFLINE",
            "latitude": 50.4501,
            "longitude": 30.5234
        }
        logger.info(f"Driver {driver_id} created in in-memory storage with status {'ONLINE' if is_active else 'OFFLINE'}")

    return updated

# ========== BOT USERS MANAGEMENT ==========

@app.post("/api/bot-users", response_model=BotUserResponse, tags=["Bot Users"])
async def create_or_get_bot_user(
    user_data: BotUserCreate,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Get or create bot user by telegram_chat_id.
    Used when user first interacts with the bot.
    Returns HTTP 201 if created, HTTP 200 if retrieved existing.
    """
    repo = BotUserRepository(db)
    bot_user, created = await repo.get_or_create(
        chat_id=user_data.telegram_chat_id,
        defaults={'current_role': user_data.current_role}
    )

    # Set appropriate status code based on whether user was created or retrieved
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
    """Update bot user fields"""
    repo = BotUserRepository(db)

    # Filter out None values
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
    All operations are performed within a single database transaction to ensure atomicity.
    """
    bot_user_repo = BotUserRepository(db)
    driver_repo = DriverRepository(db)

    # Get or create bot user (this has its own transaction handling)
    bot_user, created = await bot_user_repo.get_or_create(registration.telegram_chat_id)

    # Check if already registered as driver
    if bot_user.driver_id:
        logger.info(f"Bot user {registration.telegram_chat_id} already registered as driver")
        return bot_user

    # Split name into first_name and last_name
    name_parts = registration.driver_name.strip().split(maxsplit=1)
    first_name = name_parts[0] if name_parts else "Driver"
    last_name = name_parts[1] if len(name_parts) > 1 else str(registration.telegram_chat_id)

    # Generate safe phone number from telegram_chat_id
    # Use last 10 digits to avoid exceeding phone number length limits
    chat_id_str = str(registration.telegram_chat_id)
    phone_suffix = chat_id_str[-10:] if len(chat_id_str) >= 10 else chat_id_str.zfill(10)
    phone_number = f"+{phone_suffix}"

    # Check if driver with this phone already exists (outside transaction)
    existing_driver = await driver_repo.get_by_phone_number(phone_number)

    # Perform driver creation and bot user update in a single transaction
    # Using manual transaction control to ensure atomicity
    try:
        if existing_driver:
            driver = existing_driver
            driver_id = driver.id
            logger.info(f"Found existing driver for phone {phone_number}: {driver_id}")
        else:
            # Create Driver record without auto-commit
            driver = Driver(
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                is_active=True
            )
            db.add(driver)
            await db.flush()  # Flush to get driver.id without committing
            driver_id = driver.id
            logger.info(f"Created new driver: {driver_id}")

        # Update BotUser directly without using repository method (to avoid auto-commit)
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

        # Commit the transaction (both driver create and bot user update)
        await db.commit()
        await db.refresh(bot_user)

        # Transaction succeeded, now sync with in-memory storage
        # This is CRITICAL for SQS consumer to have access to this new driver
        drivers_storage = app.state.drivers_storage
        drivers_storage[str(driver_id)] = {
            "id": str(driver_id),
            "name": registration.driver_name,
            "status": "OFFLINE",  # Start as offline
            "latitude": 50.4501,
            "longitude": 30.5234
        }

        logger.info(f"Bot user {registration.telegram_chat_id} registered as driver {driver_id}")
        return bot_user

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to register bot user as driver: chat_id={registration.telegram_chat_id} error={str(e)}")
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
    """Update driver's online/offline status"""
    repo = BotUserRepository(db)
    bot_user = await repo.get_by_chat_id(chat_id)

    if not bot_user or not bot_user.driver_id:
        raise HTTPException(status_code=404, detail="Bot user not registered as driver")

    new_status = 'online' if is_online else 'offline'
    bot_user = await repo.update_driver_status(chat_id, new_status)

    # Sync with in-memory storage (Critical for finding drivers)
    drivers_storage = app.state.drivers_storage
    driver_key = str(bot_user.driver_id)
    
    if driver_key in drivers_storage:
        drivers_storage[driver_key]["status"] = "ONLINE" if is_online else "OFFLINE"
    else:
        # [FIX] Create a basic entry if missing from memory to ensure consistency
        drivers_storage[driver_key] = {
            "id": driver_key,
            "name": bot_user.driver_name or f"Driver {driver_key}",
            "status": "ONLINE" if is_online else "OFFLINE",
            "latitude": 50.4501,  # Default to Kyiv center
            "longitude": 30.5234
        }
        
    logger.info(f"Bot user {chat_id} driver status changed to {new_status}")
    return bot_user


@app.patch("/api/bot-users/{chat_id}/active-trip", response_model=BotUserResponse, tags=["Bot Users"])
async def set_bot_user_active_trip(
    chat_id: int,
    trip_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Set or clear active trip for driver"""
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
    """Send trip request to driver (Task #41)"""
    success = await service.send_trip_request_to_driver(
        driver_id=notification.driver_id,  # Keep as string for in-memory storage
        notification=notification
    )
    
    if not success:
        # Return 400 if driver unavailable or not found
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Driver unavailable or notification failed"
        )
    
    # Track trip request in storage
    # This ensures that when the driver accepts later, we have the record
    trip_requests_storage = app.state.trip_requests_storage
    
    if notification.trip_id not in trip_requests_storage:
        trip_requests_storage[notification.trip_id] = {
            "status": "pending",
            "notified_drivers": [notification.driver_id],
            "responses": {},
            "created_at": notification.created_at.isoformat()
        }
    else:
        # [FIX] Support multiple driver notifications for the same trip 
        # instead of overwriting or dropping the notification record.
        trip_record = trip_requests_storage[notification.trip_id]
        if notification.driver_id not in trip_record.get("notified_drivers", []):
            trip_record.setdefault("notified_drivers", []).append(notification.driver_id)
            
    logger.info(f"Notification recorded for Trip {notification.trip_id} -> Driver {notification.driver_id}")
    
    return {
        "message": "Trip request sent successfully",
        "trip_id": notification.trip_id,
        "driver_id": notification.driver_id
    }

# ========== NEW ENDPOINTS (for monitoring) ==========

@app.get("/api/v1/trip-requests")
def list_trip_requests():
    """
    List all tracked trip requests (for monitoring/debugging)
    """
    trip_requests_storage = app.state.trip_requests_storage
    logger.info(f"list_trip_requests called: storage_id={id(trip_requests_storage)}, count={len(trip_requests_storage)}, keys={list(trip_requests_storage.keys())}")
    return {
        "trip_requests": trip_requests_storage,
        "count": len(trip_requests_storage)
    }


@app.get("/api/v1/trip-requests/{trip_id}")
def get_trip_request(trip_id: str):
    """
    Get specific trip request details
    """
    trip_requests_storage = app.state.trip_requests_storage
    trip_data = trip_requests_storage.get(trip_id)
    if not trip_data:
        raise HTTPException(status_code=404, detail="Trip request not found")

    return {
        "trip_id": trip_id,
        **trip_data
    }


@app.get("/drivers/{driver_id}/trips")
async def get_driver_trips(driver_id: str):
    """
    Get available trips for driver (only pending trips that are not yet assigned)
    Used by Telegram bot "My Orders" button
    """
    # Use storage from app.state (shared with consumers), fallback to globals
    try:
        drivers_storage = app.state.drivers_storage
        trip_requests_storage = app.state.trip_requests_storage
    except AttributeError:
        # Fallback to global storage if app.state not initialized yet
        drivers_storage = drivers
        trip_requests_storage = trip_requests

    logger.info(f"get_driver_trips: trip_requests_storage has {len(trip_requests_storage)} trips")

    # Verify driver exists
    if driver_id not in drivers_storage:
        raise HTTPException(status_code=404, detail="Driver not found")

    # Get only PENDING trips (not assigned yet)
    # Exclude assigned/completed trips to prevent showing them again
    available_trips = []
    for trip_id, trip_data in trip_requests_storage.items():
        status = trip_data.get("status")
        assigned_driver_id = trip_data.get("assigned_driver_id")

        logger.info(f"  Trip {trip_id}: status={status}, assigned_driver={assigned_driver_id}")

        # Include ONLY pending trips (not yet assigned to anyone)
        if status == "pending":
            pickup_data = trip_data.get("pickup", {})
            dropoff_data = trip_data.get("dropoff", {})

            logger.info(f"  ✅ Trip {trip_id}: PENDING, pickup={pickup_data}, dropoff={dropoff_data}")

            available_trips.append({
                "trip_id": trip_id,
                "pickup": pickup_data.get("address", "N/A"),
                "dropoff": dropoff_data.get("address", "N/A"),
                "pickup_address": pickup_data.get("address", "N/A"),
                "dropoff_address": dropoff_data.get("address", "N/A"),
                "status": "PENDING",
                "comment": None,
                "created_at": trip_data.get("created_at", "")
            })
        else:
            logger.info(f"  ❌ Trip {trip_id}: status={status}, assigned_to={assigned_driver_id}, skipping (not pending)")

    logger.info(f"Driver {driver_id} requested trips: {len(available_trips)} available")

    return {
        "trips": available_trips,
        "count": len(available_trips)
    }


@app.post("/drivers/{driver_id}/trips/{trip_id}/accept")
async def accept_trip(driver_id: str, trip_id: str, db: AsyncSession = Depends(get_db)):
    """
    Driver accepts trip request
    Used by Telegram bot "Accept" button
    """
    if not response_service:
        raise HTTPException(
            status_code=503,
            detail="Response service not initialized"
        )

    # Use storage from app.state
    drivers_storage = app.state.drivers_storage
    trip_requests_storage = app.state.trip_requests_storage

    # Verify driver exists in database and sync to memory if needed
    from uuid import UUID
    try:
        driver_uuid = UUID(driver_id)
        driver_repo = DriverRepository(db)
        driver = await driver_repo.get_by_id(driver_uuid)
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found in database")

        # Ensure driver is in memory storage
        if driver_id not in drivers_storage:
            logger.warning(f"Driver {driver_id} not in memory storage, adding now")
            drivers_storage[driver_id] = {
                "id": driver_id,
                "name": f"{driver.first_name} {driver.last_name}",
                "status": "ONLINE" if driver.is_active else "OFFLINE",
                "latitude": 50.4501,
                "longitude": 30.5234
            }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid driver ID format")

    # Verify trip exists
    if trip_id not in trip_requests_storage:
        raise HTTPException(status_code=404, detail="Trip request not found")

    # Process acceptance
    # [IMPORTANT] This calls handle_driver_accept which now uses SQSPublisher!
    from datetime import datetime, timezone
    success = await response_service.handle_driver_accept(
        driver_id=driver_id,
        trip_id=trip_id,
        timestamp=datetime.now(timezone.utc)
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to process trip acceptance"
        )

    trip_data = trip_requests_storage.get(trip_id, {})

    pickup_address = trip_data.get("pickup", {}).get("address", "N/A")
    dropoff_address = trip_data.get("dropoff", {}).get("address", "N/A")

    logger.info(f"Returning trip data: trip_id={trip_id}, pickup={pickup_address}, dropoff={dropoff_address}, trip_data={trip_data}")

    return {
        "message": "Trip accepted successfully",
        "trip_id": trip_id,
        "driver_id": driver_id,
        "pickup_address": pickup_address,
        "dropoff_address": dropoff_address
    }


@app.post("/drivers/{driver_id}/trips/{trip_id}/reject")
async def reject_trip(driver_id: str, trip_id: str, db: AsyncSession = Depends(get_db)):
    """
    Driver rejects trip request. 
    Used by Telegram bot "Reject" button.
    """
    from uuid import UUID
    from datetime import datetime, timezone

    if not response_service:
        raise HTTPException(
            status_code=503,
            detail="Response service not initialized"
        )

    # Use storage from app.state
    drivers_storage = app.state.drivers_storage
    trip_requests_storage = app.state.trip_requests_storage

    # Verify driver in DB and sync with memory
    try:
        driver_uuid = UUID(driver_id)
        driver_repo = DriverRepository(db)
        driver = await driver_repo.get_by_id(driver_uuid)
        
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found in database")

        # Update memory storage if driver is not present
        if driver_id not in drivers_storage:
            logger.warning(f"Driver {driver_id} not in memory storage, adding now")
            drivers_storage[driver_id] = {
                "id": driver_id,
                "name": f"{driver.first_name} {driver.last_name}",
                "status": "ONLINE" if driver.is_active else "OFFLINE",
                "latitude": 50.4501,  # Default coordinates (Kyiv)
                "longitude": 30.5234
            }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid driver ID format")

    # Check for the existence of the trip request
    if trip_id not in trip_requests_storage:
        raise HTTPException(status_code=404, detail="Trip request not found")

    # Process rejection via response service
    success = await response_service.handle_driver_reject(
        driver_id=driver_id,
        trip_id=trip_id,
        timestamp=datetime.now(timezone.utc)
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to process trip rejection"
        )

    return {
        "message": "Trip rejected successfully",
        "trip_id": trip_id,
        "driver_id": driver_id
    }


@app.post("/drivers/{driver_id}/trips/{trip_id}/complete")
async def complete_trip(driver_id: str, trip_id: str, db: AsyncSession = Depends(get_db)):
    """
    Driver completes trip.
    Used by Telegram bot "Finish Trip" button.
    """
    from uuid import UUID
    from datetime import datetime, timezone

    # Access local storage from app state
    drivers_storage = app.state.drivers_storage
    trip_requests_storage = app.state.trip_requests_storage

    # 1. Verify driver exists in database and sync to memory storage if needed
    try:
        driver_uuid = UUID(driver_id)
        driver_repo = DriverRepository(db)
        driver = await driver_repo.get_by_id(driver_uuid)
        
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found in database")

        # Ensure driver is present in memory storage for consistent state
        if driver_id not in drivers_storage:
            logger.info(f"Syncing driver {driver_id} from DB to memory storage")
            drivers_storage[driver_id] = {
                "id": driver_id,
                "name": f"{driver.first_name} {driver.last_name}",
                "status": "ONLINE" if driver.is_active else "OFFLINE",
                "latitude": 50.4501,  # Default Kyiv coordinates
                "longitude": 30.5234
            }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid driver ID format")

    # 2. Check if response service is initialized
    if not response_service:
        raise HTTPException(
            status_code=503, 
            detail="Response service not initialized"
        )

    # 3. Process completion via DriverResponseService
    # This now handles both SQS event publishing and local status updates
    success = await response_service.handle_trip_completion(
        driver_id=driver_id,
        trip_id=trip_id,
        timestamp=datetime.now(timezone.utc)
    )

    if not success:
        raise HTTPException(
            status_code=500, 
            detail="Failed to process trip completion or publish SQS event"
        )

    return {
        "message": "Trip marked as completed and event published to SQS",
        "trip_id": trip_id,
        "driver_id": driver_id,
        "status": "completed"
    }


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring and load balancers"""
    return {"status": "healthy"}


@app.get("/")
def root():
    """Root endpoint with dynamic service and feature status"""
    return {
        "service": "Driver Service",
        "version": "0.2.0",
        "status": "running",
        "features": {
            "driver_management": True,
            "trip_requests": True,
            "driver_responses": True,
            # [FIX] Reflect actual runtime status rather than hardcoded True
            "sqs_enabled": sqs_publisher is not None,
            # [FIX] Use bool() to handle empty strings correctly from settings
            "rabbitmq_consumers": bool(settings.RABBITMQ_HOST)
        }
    }
