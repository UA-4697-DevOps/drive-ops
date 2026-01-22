import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import UUID
from typing import Optional
from fastapi import FastAPI, HTTPException, status, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

# Імпорти модулів проекту
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

# Імпорти для Task #41
from src.schemas.trip_request import TripRequestNotification
from src.services.driver_notification_service import DriverNotificationService
from src.clients.gateway_client import ClientGatewayClient
from src.clients.rabbitmq_publisher import RabbitMQPublisher
from src.services.driver_response_service import DriverResponseService

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# In-memory storage (will be replaced with database)
# NOTE: These will be moved to app.state in lifespan
drivers = {}
trip_requests = {}

# Global services
gateway_client = None
notification_service = None
rabbitmq_publisher = None
response_service = None
# FIXED: Store consumer instances globally for graceful shutdown
trip_events_consumer = None
driver_responses_consumer = None
trip_events_consumer_task = None
driver_responses_consumer_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app"""
    global gateway_client, notification_service, rabbitmq_publisher, response_service
    global trip_events_consumer, driver_responses_consumer
    global trip_events_consumer_task, driver_responses_consumer_task

    # Startup
    logger.info("Starting Driver Service...")

    # Store references in app.state for endpoints
    app.state.drivers_storage = drivers
    app.state.trip_requests_storage = trip_requests

    logger.info(f"Lifespan: Set app.state.trip_requests_storage (id={id(trip_requests)})")

    # Initialize Gateway Client
    gateway_client = ClientGatewayClient(
        base_url=settings.CLIENT_GATEWAY_URL,
        timeout=settings.GATEWAY_TIMEOUT
    )

    # Initialize Notification Service (using in-memory storage for now)
    notification_service = DriverNotificationService(
        gateway_client=gateway_client,
        drivers_storage=drivers,
        max_retries=settings.MAX_RETRY_ATTEMPTS
    )

    # NOTE: Removed seed_test_drivers() - using database now
    # Drivers should be registered via API endpoints

    # Start RabbitMQ consumers if enabled
    if settings.RABBITMQ_HOST:
        try:
            # Initialize RabbitMQ Publisher
            rabbitmq_publisher = RabbitMQPublisher(
                rabbitmq_host=settings.RABBITMQ_HOST,
                rabbitmq_port=settings.RABBITMQ_PORT,
                rabbitmq_user=settings.RABBITMQ_USER,
                rabbitmq_pass=settings.RABBITMQ_PASS,
                exchange_name=settings.TRIP_EVENTS_EXCHANGE
            )
            rabbitmq_publisher.connect()
            logger.info("RabbitMQ Publisher initialized")

            # Initialize Driver Response Service
            response_service = DriverResponseService(
                publisher=rabbitmq_publisher,
                drivers_storage=drivers,
                trip_requests_storage=trip_requests
            )
            logger.info("Driver Response Service initialized")

            # Start Trip Events Consumer
            from consumers.trip_events_consumer import TripEventsConsumer
            logger.info(f"Creating TripEventsConsumer with trip_requests storage_id={id(trip_requests)}")
            trip_events_consumer = TripEventsConsumer(
                rabbitmq_host=settings.RABBITMQ_HOST,
                rabbitmq_port=settings.RABBITMQ_PORT,
                rabbitmq_user=settings.RABBITMQ_USER,
                rabbitmq_pass=settings.RABBITMQ_PASS,
                queue_name=settings.TRIP_EVENTS_QUEUE,
                notification_service=notification_service,
                trip_requests_storage=trip_requests
            )
            logger.info(f"TripEventsConsumer created, internal storage_id={id(trip_events_consumer.trip_requests)}")
            trip_events_consumer_task = asyncio.create_task(
                asyncio.to_thread(trip_events_consumer.start_consuming)
            )
            logger.info("Trip Events Consumer started")

            # Start Driver Responses Consumer
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
            logger.info("Driver Responses Consumer started")

        except Exception as e:
            logger.error(f"Failed to start RabbitMQ consumers: {e}")

    logger.info("Driver Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Driver Service...")

    # FIXED: Call stop() on consumers before cancelling tasks
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

    if rabbitmq_publisher:
        rabbitmq_publisher.close()

    if gateway_client:
        await gateway_client.close()

    logger.info("Driver Service stopped")

app = FastAPI(
    title="DriverService",
    version="0.1.0",
    lifespan=lifespan
)

# Хелпер для сервісу
def get_notification_service():
    """Return the global notification service instance"""
    return notification_service

# ========== DEBUGGING & STATUS ENDPOINTS ==========

@app.get("/drivers/status/online", response_model=list[DriverResponse], tags=["Debugging"])
async def get_online_drivers(db: AsyncSession = Depends(get_db)):
    """
    Отримати список усіх активних водіїв (is_active=True).
    Використовується для перевірки перед відправкою Trip Request.
    """
    repo = DriverRepository(db)
    drivers = await repo.list_all()
    # Фільтруємо за полем is_active
    online_drivers = [d for d in drivers if getattr(d, 'is_active', False)]
    
    logger.info(f"🔍 Debug: Found {len(online_drivers)} online drivers")
    return online_drivers

# ========== CRUD ENDPOINTS (Database) ==========

@app.post("/drivers", response_model=DriverResponse, status_code=status.HTTP_201_CREATED, tags=["Drivers"])
async def register_driver(driver_in: DriverCreate, db: AsyncSession = Depends(get_db)):
    """Реєстрація нового водія (або повернення існуючого якщо вже зареєстрований)"""
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

    # Sync with in-memory storage for notification service
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
    """Список усіх водіїв"""
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
    """Зміна активності водія"""
    repo = DriverRepository(db)
    updated = await repo.update(driver_id, is_active=is_active)
    if not updated:
        raise HTTPException(status_code=404, detail="Driver not found")

    # Sync with in-memory storage for notification service
    drivers_storage = app.state.drivers_storage
    driver_key = str(driver_id)
    if driver_key in drivers_storage:
        drivers_storage[driver_key]["status"] = "ONLINE" if is_active else "OFFLINE"
        logger.info(f"Driver {driver_id} status updated to {'ONLINE' if is_active else 'OFFLINE'} in in-memory storage")
    else:
        # Create entry if it doesn't exist
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

    # Sync with in-memory storage
    drivers_storage = app.state.drivers_storage
    driver_key = str(bot_user.driver_id)
    if driver_key in drivers_storage:
        drivers_storage[driver_key]["status"] = "ONLINE" if is_online else "OFFLINE"

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
    """Надсилання запиту на поїздку водію (Task #41)"""
    success = await service.send_trip_request_to_driver(
        driver_id=notification.driver_id,  # Keep as string for in-memory storage
        notification=notification
    )
    
    if not success:
        # Повертаємо 400, якщо водій не в мережі або не знайдений
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Driver unavailable or notification failed"
        )
    
    # NEW: Track trip request in storage
    trip_requests_storage = app.state.trip_requests_storage
    if notification.trip_id not in trip_requests_storage:
        trip_requests_storage[notification.trip_id] = {
            "status": "pending",
            "notified_drivers": [notification.driver_id],
            "responses": {},
            "created_at": notification.created_at.isoformat()
        }
    
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
    Driver rejects trip request
    Used by Telegram bot "Reject" button
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

    # Process rejection
    from datetime import datetime, timezone
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
    Driver completes trip
    Used by Telegram bot "Finish Trip" button
    """
    from datetime import datetime, timezone
    from uuid import UUID

    # Use storage from app.state
    drivers_storage = app.state.drivers_storage
    trip_requests_storage = app.state.trip_requests_storage

    # Verify driver exists in database
    try:
        driver_uuid = UUID(driver_id)
        driver_repo = DriverRepository(db)
        driver = await driver_repo.get_by_id(driver_uuid)
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found in database")

        # Ensure driver is in memory storage for RabbitMQ events
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

    # Update local storage if trip exists there
    previous_status = None
    if trip_id in trip_requests_storage:
        previous_status = trip_requests_storage[trip_id]["status"]
        trip_requests_storage[trip_id]["status"] = "completed"
        logger.info(f"Trip {trip_id} marked as completed in local storage by driver {driver_id} (previous status: {previous_status})")
    else:
        logger.info(f"Trip {trip_id} not in local storage (likely after restart), will send completion event to trip-service")

    # Track event publishing status
    event_published = False
    event_warning = None

    # Publish trip.event.completed to RabbitMQ so trip-service can update its database
    if rabbitmq_publisher:
        # Use UTC timestamp with Z suffix (RFC3339 format for Go)
        # datetime.now(timezone.utc).isoformat() returns format with +00:00, convert to Z for Go
        completed_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        payload = {
            "trip_id": trip_id,
            "driver_id": driver_id,
            "completed_at": completed_at
        }

        # Retry logic: 3 attempts with exponential backoff
        max_retries = 3
        retry_delay = 0.5  # Start with 500ms

        for attempt in range(1, max_retries + 1):
            try:
                # Capture return value to detect silent failures
                success = rabbitmq_publisher.publish_event(
                    event_type="trip.event.completed",
                    payload=payload,
                    routing_key="trip.event.completed"
                )

                # Treat False return as failure
                if success is False:
                    raise RuntimeError("RabbitMQ publisher returned False indicating publish failure")

                logger.info(f"✅ Published trip.event.completed for trip {trip_id} to RabbitMQ (attempt {attempt})")
                event_published = True
                break
            except Exception as e:
                logger.error(
                    f"❌ Failed to publish trip.event.completed (attempt {attempt}/{max_retries}) for trip_id={trip_id}, "
                    f"driver_id={driver_id}: {type(e).__name__}: {str(e)}",
                    exc_info=True
                )

                if attempt < max_retries:
                    # Wait before retry with exponential backoff (async to avoid blocking event loop)
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Double the delay for next attempt
                else:
                    # All retries failed - rollback the status change if trip is in local storage
                    if trip_id in trip_requests_storage and previous_status:
                        logger.error(
                            f"🔄 Rolling back trip {trip_id} status from 'completed' to '{previous_status}' "
                            f"due to event publishing failure after {max_retries} attempts"
                        )
                        trip_requests_storage[trip_id]["status"] = previous_status
                    else:
                        logger.error(
                            f"❌ Failed to publish trip completion event for trip {trip_id} after {max_retries} attempts. "
                            f"Trip not in local storage, cannot rollback."
                        )

                    event_warning = (
                        f"Trip status could not be synchronized with trip-service due to messaging failure. "
                        f"Please try again or contact support."
                    )

    # Build response with warning if event publishing failed
    current_status = trip_requests_storage[trip_id]["status"] if trip_id in trip_requests_storage else "unknown"
    response = {
        "message": "Trip completed successfully" if event_published else "Trip completion failed - status not synchronized",
        "trip_id": trip_id,
        "driver_id": driver_id,
        "status": current_status,
        "event_published": event_published
    }

    # Only add warning if there was an actual failure
    if event_warning:
        response["warning"] = event_warning

    return response


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/")
def root():
    """Root endpoint with service info"""
    return {
        "service": "Driver Service",
        "version": "0.2.0",
        "status": "running",
        "features": {
            "driver_management": True,
            "trip_requests": True,
            "driver_responses": True,
            "rabbitmq_enabled": settings.RABBITMQ_HOST is not None
        }
    }
