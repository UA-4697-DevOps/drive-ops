import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# Імпорти модулів проекту
from src.database import get_db
from src.services.driver_repository import DriverRepository
from src.schemas.driver_schemas import DriverCreate, DriverResponse
from src.config import settings

# Імпорти для Task #41
from src.schemas.trip_request import TripRequestNotification
from src.services.driver_notification_service import DriverNotificationService
from src.clients.gateway_client import ClientGatewayClient

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
    """Менеджер життєвого циклу додатка (Startup/Shutdown)"""
    global _gateway_client, _consumer_task
    
    # Startup
    logger.info("Starting Driver Service...")

    # Store references in app.state for endpoints
    app.state.drivers_storage = drivers
    app.state.trip_requests_storage = trip_requests

    # Initialize Gateway Client
    gateway_client = ClientGatewayClient(
        base_url=settings.CLIENT_GATEWAY_URL,
        timeout=settings.GATEWAY_TIMEOUT
    )
    
    # 2. Запуск RabbitMQ споживача
    if settings.ENABLE_RABBITMQ:
        try:
            from src.consumers.trip_events_consumer import TripEventsConsumer
            consumer = TripEventsConsumer(
                rabbitmq_host=settings.RABBITMQ_HOST,
                gateway_client=_gateway_client
            )
            _consumer_task = asyncio.create_task(asyncio.to_thread(consumer.start_consuming))
            logger.info("🐰 RabbitMQ consumer started")
        except Exception as e:
            logger.error(f"❌ Failed to start RabbitMQ consumer: {e}")
    
    yield
    
    # --- Shutdown ---
    logger.info("🛑 Shutting down Driver Service...")
    if _gateway_client:
        await _gateway_client.close()
    if _consumer_task:
        _consumer_task.cancel()

app = FastAPI(
    title="DriverService",
    version="0.1.0",
    lifespan=lifespan
)

# Хелпер для сервісу
def get_notification_service(db: AsyncSession = Depends(get_db)):
    return DriverNotificationService(
        gateway_client=_gateway_client,
        session=db,
        max_retries=settings.MAX_RETRY_ATTEMPTS
    )

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
    """Реєстрація нового водія"""
    repo = DriverRepository(db)
    return await repo.create(**driver_in.model_dump())

@app.get("/drivers", response_model=list[DriverResponse], tags=["Drivers"])
async def list_drivers(db: AsyncSession = Depends(get_db)):
    """Список усіх водіїв"""
    repo = DriverRepository(db)
    return await repo.list_all()

@app.get("/drivers/{driver_id}", response_model=DriverResponse, tags=["Drivers"])
async def get_driver(driver_id: int, db: AsyncSession = Depends(get_db)):
    repo = DriverRepository(db)
    driver = await repo.get_by_id(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver

@app.patch("/drivers/{driver_id}/status", response_model=DriverResponse, tags=["Drivers"])
async def update_driver_status(driver_id: int, is_active: bool, db: AsyncSession = Depends(get_db)):
    """Зміна активності водія"""
    repo = DriverRepository(db)
    updated = await repo.update(driver_id, is_active=is_active)
    if not updated:
        raise HTTPException(status_code=404, detail="Driver not found")
    return updated

# ========== TASK #41: TRIP REQUESTS ==========

@app.post("/api/v1/trip-requests/send", status_code=status.HTTP_202_ACCEPTED, tags=["Trip Requests"])
async def send_trip_request(
    notification: TripRequestNotification,
    service: DriverNotificationService = Depends(get_notification_service)
):
    """Надсилання запиту на поїздку водію (Task #41)"""
    success = await service.send_trip_request_to_driver(
        driver_id=int(notification.driver_id),
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
    Get available trips for driver (pending trips)
    Used by Telegram bot "My Orders" button
    """
    # Use storage from app.state (shared with consumers)
    drivers_storage = app.state.drivers_storage
    trip_requests_storage = app.state.trip_requests_storage

    # Verify driver exists
    if driver_id not in drivers_storage:
        raise HTTPException(status_code=404, detail="Driver not found")

    # Get all pending trips
    available_trips = []
    for trip_id, trip_data in trip_requests_storage.items():
        if trip_data.get("status") == "pending":
            available_trips.append({
                "trip_id": trip_id,
                "pickup": trip_data.get("pickup", {}).get("address", "N/A"),
                "dropoff": trip_data.get("dropoff", {}).get("address", "N/A"),
                "pickup_address": trip_data.get("pickup", {}).get("address", "N/A"),
                "dropoff_address": trip_data.get("dropoff", {}).get("address", "N/A"),
                "comment": None,
                "created_at": trip_data.get("created_at", "")
            })

    logger.info(f"Driver {driver_id} requested trips: {len(available_trips)} available")

    return {
        "trips": available_trips,
        "count": len(available_trips)
    }


@app.post("/drivers/{driver_id}/trips/{trip_id}/accept")
async def accept_trip(driver_id: str, trip_id: str):
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

    # Verify driver exists
    if driver_id not in drivers_storage:
        raise HTTPException(status_code=404, detail="Driver not found")

    # Verify trip exists
    if trip_id not in trip_requests_storage:
        raise HTTPException(status_code=404, detail="Trip request not found")

    # Process acceptance
    from datetime import datetime
    success = await response_service.handle_driver_accept(
        driver_id=driver_id,
        trip_id=trip_id,
        timestamp=datetime.now()
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to process trip acceptance"
        )

    trip_data = trip_requests_storage.get(trip_id, {})

    return {
        "message": "Trip accepted successfully",
        "trip_id": trip_id,
        "driver_id": driver_id,
        "pickup_address": trip_data.get("pickup", {}).get("address", "N/A"),
        "dropoff_address": trip_data.get("dropoff", {}).get("address", "N/A")
    }


@app.post("/drivers/{driver_id}/trips/{trip_id}/reject")
async def reject_trip(driver_id: str, trip_id: str):
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

    # Verify driver exists
    if driver_id not in drivers_storage:
        raise HTTPException(status_code=404, detail="Driver not found")

    # Verify trip exists
    if trip_id not in trip_requests_storage:
        raise HTTPException(status_code=404, detail="Trip request not found")

    # Process rejection
    from datetime import datetime
    success = await response_service.handle_driver_reject(
        driver_id=driver_id,
        trip_id=trip_id,
        timestamp=datetime.now()
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
            "rabbitmq_enabled": settings.ENABLE_RABBITMQ
        }
    }
