import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status, Depends
from uuid import uuid4, UUID
from typing import Optional, List

# SQLAlchemy imports
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Внутрішні імпорти
from schemas.trip_request import TripRequestNotification
from services.driver_notification_service import DriverNotificationService
from clients.gateway_client import ClientGatewayClient
from config import settings
from clients.rabbitmq_publisher import RabbitMQPublisher
from services.driver_response_service import DriverResponseService
from repository.driver_repository import DriverRepository
from models.driver import Base, DriverModel, DriverCreate, DriverUpdateLocation

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] | [%(levelname)s] | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)

# --- Database Setup ---
DATABASE_URL = f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DRIVER_DB_NAME}"
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Глобальні об'єкти сервісів
gateway_client = None
notification_service = None
rabbitmq_publisher = None
response_service = None
background_tasks = set()

# Dependency для отримання сесії БД в ендпоінти
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager (Tasks 1, 2, 3, 4)"""
    global gateway_client, notification_service, rabbitmq_publisher, response_service
    
    logger.info("🚀 Запуск Driver Service з підтримкою БД...")
    
    # 1. Ініціалізація клієнтів
    gateway_client = ClientGatewayClient(
        base_url=settings.CLIENT_GATEWAY_URL,
        timeout=settings.GATEWAY_TIMEOUT
    )
    
    # 2. RabbitMQ Publisher (для Phase 3)
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
            logger.info("✅ RabbitMQ Publisher готовий")
        except Exception as e:
            logger.error(f"❌ Помилка RabbitMQ: {e}")

    # 3. Ініціалізація сервісів (передаємо SessionLocal для консюмерів)
    notification_service = DriverNotificationService(
        gateway_client=gateway_client,
        session_factory=AsyncSessionLocal,
        max_retries=settings.MAX_RETRY_ATTEMPTS
    )
    
    response_service = DriverResponseService(
        publisher=rabbitmq_publisher,
        session_factory=AsyncSessionLocal
    )

    # 4. Запуск RabbitMQ Consumers (Phase 2 & 3)
    if settings.ENABLE_RABBITMQ:
        from consumers.trip_events_consumer import TripEventsConsumer
        from consumers.driver_response_consumer import DriverResponseConsumer

        trip_consumer = TripEventsConsumer(
            settings, notification_service, AsyncSessionLocal
        )
        resp_consumer = DriverResponseConsumer(
            settings, response_service
        )

        for c in [trip_consumer, resp_consumer]:
            task = asyncio.create_task(asyncio.to_thread(c.start_consuming))
            background_tasks.add(task)

    yield
    
    # --- Shutdown ---
    logger.info("🛑 Зупинка Driver Service...")
    if rabbitmq_publisher:
        rabbitmq_publisher.close()
    await gateway_client.close()
    await engine.dispose()

app = FastAPI(title="DriverService", version="1.0.0", lifespan=lifespan)

# ========== API Ендпоінти (Task 5) ==========

@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    repo = DriverRepository(db)
    online_count = await repo.count_online_drivers()
    return {"status": "ok", "drivers_online": online_count}

@app.post("/drivers", status_code=201)
async def register_driver(data: DriverCreate, db: AsyncSession = Depends(get_db)):
    """Реєстрація водія в БД (Task 3)"""
    repo = DriverRepository(db)
    
    # Перевірка чи не зареєстрований вже такий telegram_id
    existing = await repo.get_by_telegram_id(data.telegram_id)
    if existing:
        return existing

    new_driver = DriverModel(
        id=uuid4(),
        name=data.name,
        car_description=data.car_description,
        telegram_id=data.telegram_id,
        status="OFFLINE"
    )
    return await repo.create(new_driver)

@app.post("/drivers/{driver_id}/status")
async def update_status(driver_id: UUID, status: str, db: AsyncSession = Depends(get_db)):
    """Оновлення статусу водія в БД"""
    repo = DriverRepository(db)
    updated_driver = await repo.update_status(driver_id, status.upper())
    if not updated_driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return updated_driver

@app.post("/drivers/{driver_id}/location")
async def update_location(driver_id: UUID, data: DriverUpdateLocation, db: AsyncSession = Depends(get_db)):
    """Оновлення гео-позиції (Task 5)"""
    repo = DriverRepository(db)
    try:
        lat, lon = map(float, data.location.split(','))
        await repo.update_location(driver_id, lat, lon)
        return {"status": "location_updated"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid location format. Expected 'lat,lon'")

@app.get("/drivers/{driver_id}")
async def get_driver(driver_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = DriverRepository(db)
    driver = await repo.get_by_id(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver

@app.get("/drivers")
async def list_drivers(status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    repo = DriverRepository(db)
    return await repo.list_all(status=status.upper() if status else None)

# Ендпоінт для сідінгу (Task 3)
@app.post("/api/v1/internal/seed-drivers")
async def seed_drivers(db: AsyncSession = Depends(get_db)):
    repo = DriverRepository(db)
    demo_driver = DriverModel(
        id=uuid4(),
        name="Демо Олександр",
        car_description="Skoda Octavia White",
        status="AVAILABLE",
        telegram_id="11223344"
    )
    await repo.create(demo_driver)
    return {"message": "Demo driver seeded into Postgres"}
