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

# NEW: Import for driver response handling
from clients.rabbitmq_publisher import RabbitMQPublisher
from services.driver_response_service import DriverResponseService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# In-memory storage (will be replaced with database)
drivers = {}
trip_requests = {}  # NEW: Track trip requests for idempotency

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
    
    # Start RabbitMQ consumers if enabled
    if settings.ENABLE_RABBITMQ:
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
            
            # Start Trip Events Consumer (existing)
            from consumers.trip_events_consumer import TripEventsConsumer
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
            logger.info("Trip Events Consumer started")
            
            # Start Driver Responses Consumer (NEW)
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
    version="0.2.0",
    description="Driver Service with Trip Request and Response functionality",
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
    
    # NEW: Track trip request in storage
    if notification.trip_id not in trip_requests:
        trip_requests[notification.trip_id] = {
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
    return {
        "trip_requests": trip_requests,
        "count": len(trip_requests)
    }


@app.get("/api/v1/trip-requests/{trip_id}")
def get_trip_request(trip_id: str):
    """
    Get specific trip request details
    """
    trip_data = trip_requests.get(trip_id)
    if not trip_data:
        raise HTTPException(status_code=404, detail="Trip request not found")
    
    return {
        "trip_id": trip_id,
        **trip_data
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
