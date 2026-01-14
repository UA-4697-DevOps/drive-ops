import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from uuid import uuid4

# Import schemas and services for task #41
from schemas.trip_request import TripRequestNotification
from services.driver_notification_service import DriverNotificationService
from clients.gateway_client import ClientGatewayClient
from config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# In-memory storage (will be replaced with database)
drivers = {}

# Global services
gateway_client = None
notification_service = None
consumer_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app"""
    global gateway_client, notification_service, consumer_task
    
    # Startup
    logger.info("Starting Driver Service...")
    
    # Initialize Gateway Client
    gateway_client = ClientGatewayClient(
        base_url=settings.CLIENT_GATEWAY_URL,
        timeout=settings.GATEWAY_TIMEOUT
    )
    
    # Initialize Notification Service
    notification_service = DriverNotificationService(
        gateway_client=gateway_client,
        drivers_storage=drivers,
        max_retries=settings.MAX_RETRY_ATTEMPTS
    )
    
    # Seed some test drivers
    seed_test_drivers()
    
    # Start RabbitMQ consumer if enabled
    if settings.ENABLE_RABBITMQ:
        try:
            from consumers.trip_events_consumer import TripEventsConsumer
            consumer = TripEventsConsumer(
                rabbitmq_host=settings.RABBITMQ_HOST,
                rabbitmq_port=settings.RABBITMQ_PORT,
                rabbitmq_user=settings.RABBITMQ_USER,
                rabbitmq_pass=settings.RABBITMQ_PASS,
                queue_name=settings.TRIP_EVENTS_QUEUE,
                notification_service=notification_service
            )
            consumer_task = asyncio.create_task(
                asyncio.to_thread(consumer.start_consuming)
            )
            logger.info("RabbitMQ consumer started")
        except Exception as e:
            logger.error(f"Failed to start RabbitMQ consumer: {e}")
    
    logger.info("Driver Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Driver Service...")
    
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
    
    if gateway_client:
        await gateway_client.close()
    
    logger.info("Driver Service stopped")


def seed_test_drivers():
    # Seed some test drivers into in-memory storage
    test_drivers = [
        {
            "id": "driver_001",
            "name": "Олександр Коваленко",
            "phone": "+380501234567",
            "status": "AVAILABLE",
            "location": "50.4501,30.5234",  # Київ, Хрещатик
            "rating": 4.8,
            "total_trips": 150
        },
        {
            "id": "driver_002",
            "name": "Марія Шевченко",
            "phone": "+380502345678",
            "status": "AVAILABLE",
            "location": "50.4520,30.5245",  # Київ, центр
            "rating": 4.9,
            "total_trips": 200
        },
        {
            "id": "driver_003",
            "name": "Дмитро Петренко",
            "phone": "+380503456789",
            "status": "OFFLINE",
            "location": "50.4480,30.5210",  # Київ, Поділ
            "rating": 4.7,
            "total_trips": 120
        },
    ]
    
    for driver in test_drivers:
        drivers[driver["id"]] = driver
    
    logger.info(f"Seeded {len(test_drivers)} test drivers")


app = FastAPI(
    title="DriverService",
    version="0.1.0",
    description="Driver Service with Trip Request functionality",
    lifespan=lifespan
)


# ========== EXISTING ENDPOINTS (from original main.py) ==========

@app.get("/health")
def health():
    """Health check endpoint"""
    return {"status": "ok"}


@app.post("/drivers", status_code=201)
def register_driver():
    """Register a new driver"""
    driver_id = str(uuid4())

    driver = {
        "id": driver_id,
        "status": "OFFLINE",
        "location": None
    }

    drivers[driver_id] = driver
    return driver


@app.get("/drivers/{driver_id}")
def get_driver(driver_id: str):
    """Get driver by ID"""
    driver = drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


@app.post("/drivers/{driver_id}/status")
def update_status(driver_id: str, status: str):
    """Update driver status"""
    driver = drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    if status not in ["ONLINE", "OFFLINE", "AVAILABLE", "ON_TRIP", "NOTIFIED"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    driver["status"] = status
    return driver


@app.post("/drivers/{driver_id}/location")
def update_location(driver_id: str, location: str):
    """Update driver location"""
    driver = drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    driver["location"] = location
    return driver


# ========== NEW ENDPOINTS (for task #41) ==========

@app.get("/drivers")
def list_drivers(status: str = None):
    """
    List all drivers, optionally filtered by status
    
    Query params:
    - status: Filter by driver status (ONLINE, OFFLINE, AVAILABLE, etc.)
    """
    if status:
        filtered = {k: v for k, v in drivers.items() if v.get("status") == status}
        return {"drivers": list(filtered.values()), "count": len(filtered)}
    
    return {"drivers": list(drivers.values()), "count": len(drivers)}


@app.post("/api/v1/trip-requests/send", status_code=status.HTTP_202_ACCEPTED)
async def send_trip_request(notification: TripRequestNotification):
    """
    Send trip request command to driver (Task #41)
    
    This endpoint is for manual testing. In production, this is triggered
    by consuming trip.event.created from RabbitMQ.
    
    Body:
    - trip_id: Unique trip identifier
    - driver_id: Target driver ID
    - pickup: Pickup location with coordinates
    - dropoff: Dropoff location with coordinates
    - passenger_name: Name of passenger
    - estimated_distance_km: Distance estimate
    - estimated_duration_min: Duration estimate
    - fare_estimate: Price estimate
    - comment: Optional comment
    """
    if not notification_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Notification service not initialized"
        )
    
    success = await notification_service.send_trip_request_to_driver(
        driver_id=notification.driver_id,
        notification=notification
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send trip request to driver"
        )
    
    return {
        "message": "Trip request sent successfully",
        "trip_id": notification.trip_id,
        "driver_id": notification.driver_id
    }


@app.get("/")
def root():
    """Root endpoint with service info"""
    return {
        "service": "Driver Service",
        "version": "0.1.0",
        "status": "running",
        "features": {
            "driver_management": True,
            "trip_requests": True,
            "rabbitmq_enabled": settings.ENABLE_RABBITMQ
        }
    }