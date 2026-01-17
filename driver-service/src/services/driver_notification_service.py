"""
Сервіс для обробки сповіщень водіїв та запитів на поїздку.
Тепер використовує базу даних через репозиторій.
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

# Абсолютні імпорти (через src)
from src.schemas.trip_request import TripRequestNotification
from src.clients.gateway_client import ClientGatewayClient
from src.services.driver_repository import DriverRepository
# Переконайся, що цей файл існує за шляхом src/utils/geo.py
try:
    from src.utils.geo import find_nearby_drivers
except ImportError:
    # Заглушка, якщо файл geo ще не створено
    def find_nearby_drivers(*args, **kwargs): return []

logger = logging.getLogger(__name__)

class DriverNotificationService:
    """Сервіс для обробки сповіщень водіїв та запитів на поїздку"""
    
    def __init__(
        self,
        gateway_client: ClientGatewayClient,
        session: AsyncSession,  # Тепер приймаємо сесію БД замість словника
        max_retries: int = 3
    ):
        self.gateway_client = gateway_client
        self.session = session
        self.repo = DriverRepository(session)
        self.max_retries = max_retries
    
    async def send_trip_request_to_driver(
        self,
        driver_id: int,  # Змінено на int, бо в БД ID зазвичай числові
        notification: TripRequestNotification
    ) -> bool:
        """Надсилає запит на поїздку конкретному водію з логікою повторів"""
        logger.info(
            f"Attempting to send trip request - Trip ID: {notification.trip_id}, Driver ID: {driver_id}"
        )
        
        # 1. Перевіряємо водія в БД
        driver = await self.repo.get_by_id(driver_id)
        if not driver:
            logger.error(f"Driver not found in DB: {driver_id}")
            return False
        
        # 2. Перевіряємо статус (припустимо, статус зберігається в driver.status або driver.is_active)
        # Якщо використовуємо is_active як на скріншотах:
        if not getattr(driver, "is_active", False):
            logger.warning(f"Driver {driver_id} is OFFLINE")
            return False
        
        # 3. Логіка повторних спроб
        for attempt in range(1, self.max_retries + 1):
            try:
                success = await self.gateway_client.send_driver_notification(
                    driver_id=str(driver_id),
                    notification=notification
                )
                
                if success:
                    logger.info(f"✅ Trip request sent to Driver {driver_id}")
                    # Оновлюємо статус в БД, якщо потрібно
                    # await self.repo.update(driver_id, status="NOTIFIED") 
                    return True
                
                logger.warning(f"⚠️ Attempt {attempt}/{self.max_retries} failed for Driver {driver_id}")
                    
            except Exception as e:
                logger.error(f"❌ Error on attempt {attempt}: {e}")
        
        return False

    async def notify_nearby_drivers(
        self,
        trip_id: str,
        pickup_latitude: float,
        pickup_longitude: float,
        notification_data: dict,
        radius_km: float = 5.0
    ) -> List[int]:
        """Знаходить та сповіщає найближчих доступних водіїв"""
        # Отримуємо всіх активних водіїв з БД
        all_drivers = await self.repo.list_all()
        
        # Перетворюємо об'єкти SQLAlchemy у формат для geo-функції, якщо вона очікує словники
        drivers_list = [
            {"id": d.id, "location": getattr(d, "location", "0,0"), "status": "AVAILABLE"} 
            for d in all_drivers if d.is_active
        ]

        nearby_drivers = find_nearby_drivers(
            drivers=drivers_list,
            pickup_lat=pickup_latitude,
            pickup_lng=pickup_longitude,
            radius_km=radius_km,
            max_drivers=10
        )
        
        if not nearby_drivers:
            logger.warning(f"No nearby drivers for trip {trip_id}")
            return []
        
        notified_drivers = []
        for d_info in nearby_drivers:
            driver_id = d_info["id"]
            
            notification = TripRequestNotification(
                trip_id=trip_id,
                driver_id=str(driver_id),
                **notification_data
            )
            
            if await self.send_trip_request_to_driver(driver_id, notification):
                notified_drivers.append(driver_id)
        
        return notified_drivers