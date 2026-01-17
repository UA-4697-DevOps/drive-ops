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
# ... (початок файлу)

# ІМПОРТИ ДЛЯ TASK #41 - ПЕРЕВІР ТУТ!
from src.schemas.trip_request import TripRequestNotification
from src.services.driver_notification_service import DriverNotificationService
from src.clients.gateway_client import ClientGatewayClient




# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальні змінні для довготривалих з'єднань
_gateway_client: ClientGatewayClient = None
_consumer_task: asyncio.Task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Менеджер життєвого циклу додатка (Startup/Shutdown)"""
    global _gateway_client, _consumer_task
    
    logger.info("🚀 Starting Driver Service...")
    
    # 1. Ініціалізація клієнта для зв'язку з іншими сервісами
    _gateway_client = ClientGatewayClient(
        base_url=settings.CLIENT_GATEWAY_URL,
        timeout=settings.GATEWAY_TIMEOUT
    )
    
    # 2. Запуск RabbitMQ споживача
    if settings.ENABLE_RABBITMQ:
        try:
            from src.consumers.trip_events_consumer import TripEventsConsumer
            # Створюємо тимчасову сесію для споживача
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

# Функція-хелпер для отримання сервісу сповіщень
def get_notification_service(db: AsyncSession = Depends(get_db)):
    return DriverNotificationService(
        gateway_client=_gateway_client,
        session=db,
        max_retries=settings.MAX_RETRY_ATTEMPTS
    )

# ========== CRUD ENDPOINTS (Database) ==========

@app.post("/drivers", response_model=DriverResponse, status_code=status.HTTP_201_CREATED)
async def register_driver(driver_in: DriverCreate, db: AsyncSession = Depends(get_db)):
    """Реєстрація нового водія"""
    repo = DriverRepository(db)
    return await repo.create(**driver_in.model_dump())

@app.get("/drivers", response_model=list[DriverResponse])
async def list_drivers(status: str = None, db: AsyncSession = Depends(get_db)):
    """Список водіїв з фільтрацією за статусом"""
    repo = DriverRepository(db)
    drivers = await repo.list_all()
    if status:
        # Приклад логіки фільтрації (можна винести в repo.list_all(status=status))
        return [d for d in drivers if d.status == status]
    return drivers

@app.get("/drivers/{driver_id}", response_model=DriverResponse)
async def get_driver(driver_id: int, db: AsyncSession = Depends(get_db)):
    repo = DriverRepository(db)
    driver = await repo.get_by_id(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver

@app.patch("/drivers/{driver_id}/status", response_model=DriverResponse)
async def update_driver_status(driver_id: int, new_status: str, db: AsyncSession = Depends(get_db)):
    """Зміна статусу водія (ONLINE, AVAILABLE, etc)"""
    repo = DriverRepository(db)
    updated = await repo.update(driver_id, status=new_status)
    if not updated:
        raise HTTPException(status_code=404, detail="Driver not found")
    return updated

# ========== TASK #41: TRIP REQUESTS ==========

@app.post("/api/v1/trip-requests/send", status_code=status.HTTP_202_ACCEPTED)
async def send_trip_request(
    notification: TripRequestNotification,
    service: DriverNotificationService = Depends(get_notification_service)
):
    """Ручне відправлення запиту на поїздку водію"""
    success = await service.send_trip_request_to_driver(
        driver_id=notification.driver_id,
        notification=notification
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not reach driver or gateway"
        )
    
    return {"status": "accepted", "trip_id": notification.trip_id}

@app.get("/health")
def health():
    return {"status": "ok", "db": "healthy"}