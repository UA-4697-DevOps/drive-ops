import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status, Body
from uuid import uuid4
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

# Імпорт схем та клієнтів
from schemas.trip_request import TripRequestNotification
from services.driver_notification_service import DriverNotificationService
from clients.gateway_client import ClientGatewayClient
from config import settings
from clients.rabbitmq_publisher import RabbitMQPublisher
from services.driver_response_service import DriverResponseService

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] | [%(levelname)s] | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)

# --- Сховище (Тимчасово в пам'яті до підключення DB) ---
drivers = {}
trip_requests = {} 

# --- Глобальні сервіси ---
gateway_client = None
notification_service = None
rabbitmq_publisher = None
response_service = None
trip_events_consumer = None
driver_responses_consumer = None
background_tasks = set()

# --- Схеми даних (DTO) ---
class DriverCreate(BaseModel):
    name: str
    car_description: str
    telegram_id: str

class DriverUpdateLocation(BaseModel):
    location: str  # Формат "lat,lng"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Керування життєвим циклом додатка (Task 1, 2, 4)"""
    global gateway_client, notification_service, rabbitmq_publisher, response_service
    global trip_events_consumer, driver_responses_consumer
    
    logger.info("🚀 Запуск Driver Service...")
    
    # 1. Клієнт для зв'язку з ботом
    gateway_client = ClientGatewayClient(
        base_url=settings.CLIENT_GATEWAY_URL,
        timeout=settings.GATEWAY_TIMEOUT
    )
    
    # 2. Сервіс пошуку та сповіщення водіїв
    notification_service = DriverNotificationService(
        gateway_client=gateway_client,
        drivers_storage=drivers,
        max_retries=settings.MAX_RETRY_ATTEMPTS
    )
    
    # 3. Тестові дані
    seed_test_drivers()
    
    # 4. RabbitMQ Інтеграція
    if settings.ENABLE_RABBITMQ:
        try:
            rabbitmq_publisher = RabbitMQPublisher(
                rabbitmq_host=settings.RABBITMQ_HOST,
                rabbitmq_port=settings.RABBITMQ_PORT,
                rabbitmq_user=settings.RABBITMQ_USER,
                rabbitmq_pass=settings.RABBITMQ_PASS,
                exchange_name=settings.TRIP_EVENTS_EXCHANGE
            )
            rabbitmq_publisher.connect()
            
            response_service = DriverResponseService(
                publisher=rabbitmq_publisher,
                drivers_storage=drivers,
                trip_requests_storage=trip_requests
            )

            # Запуск Consumer для нових поїздок (Phase 2)
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
            
            # Запуск Consumer для відповідей водіїв (Phase 3)
            from consumers.driver_response_consumer import DriverResponseConsumer
            driver_responses_consumer = DriverResponseConsumer(
                rabbitmq_host=settings.RABBITMQ_HOST,
                rabbitmq_port=settings.RABBITMQ_PORT,
                rabbitmq_user=settings.RABBITMQ_USER,
                rabbitmq_pass=settings.RABBITMQ_PASS,
                queue_name=settings.DRIVER_RESPONSES_QUEUE,
                response_service=response_service
            )

            # Запускаємо в окремих потоках, щоб не блокувати FastAPI
            for consumer in [trip_events_consumer, driver_responses_consumer]:
                task = asyncio.create_task(asyncio.to_thread(consumer.start_consuming))
                background_tasks.add(task)
                
            logger.info("✅ RabbitMQ Consumers запущені")
        except Exception as e:
            logger.error(f"❌ Помилка RabbitMQ: {e}")

    yield
    
    # --- Shutdown ---
    logger.info("Stopping Driver Service...")
    if trip_events_consumer: trip_events_consumer.stop()
    if driver_responses_consumer: driver_responses_consumer.stop()
    if rabbitmq_publisher: rabbitmq_publisher.close()
    await gateway_client.close()

# ========== Ендпоінти (Task 5) ==========

@app.get("/health")
def health():
    return {"status": "ok", "drivers_online": len([d for d in drivers.values() if d['status'] == 'ONLINE'])}

@app.post("/drivers", status_code=201)
def register_driver(data: DriverCreate):
    """Реєстрація нового водія (викликається ботом)"""
    driver_id = str(uuid4())
    new_driver = {
        "id": driver_id,
        "name": data.name,
        "car_description": data.car_description,
        "telegram_id": data.telegram_id,
        "status": "OFFLINE",
        "location": "50.4501,30.5234" # Дефолт - центр Києва
    }
    drivers[driver_id] = new_driver
    logger.info(f"Зареєстровано водія: {data.name} (ID: {driver_id})")
    return new_driver

@app.post("/drivers/{driver_id}/status")
def update_status(driver_id: str, status: str):
    """Зміна статусу (ONLINE/OFFLINE)"""
    if driver_id not in drivers:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    valid_statuses = ["ONLINE", "OFFLINE", "AVAILABLE", "ON_TRIP", "NOTIFIED"]
    if status.upper() not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {valid_statuses}")
    
    drivers[driver_id]["status"] = status.upper()
    return drivers[driver_id]

@app.post("/drivers/{driver_id}/location")
def update_location(driver_id: str, data: DriverUpdateLocation):
    """Оновлення координат водія"""
    if driver_id not in drivers:
        raise HTTPException(status_code=404, detail="Driver not found")
    drivers[driver_id]["location"] = data.location
    return {"status": "location_updated"}

@app.get("/drivers/{driver_id}")
def get_driver(driver_id: str):
    if driver_id not in drivers:
        raise HTTPException(status_code=404, detail="Driver not found")
    return drivers[driver_id]

@app.get("/drivers")
def list_drivers(status: Optional[str] = None):
    if status:
        return [d for d in drivers.values() if d['status'] == status.upper()]
    return list(drivers.values())

# ========== Допоміжні функції ==========

def seed_test_drivers():
    test_data = [
        {"id": "driver_001", "name": "Олександр", "car_description": "Toyota Camry Black", "telegram_id": "12345", "status": "AVAILABLE", "location": "50.4501,30.5234"},
        {"id": "driver_002", "name": "Марія", "car_description": "Hyundai Sonata White", "telegram_id": "67890", "status": "AVAILABLE", "location": "50.4520,30.5245"}
    ]
    for d in test_data:
        drivers[d["id"]] = d
    logger.info(f"seeded {len(test_data)} drivers")

app = FastAPI(title="DriverService", version="1.0.0", lifespan=lifespan)
