import logging
from typing import List, Dict, Any
from sqlalchemy.orm import sessionmaker

from schemas.trip_request import TripRequestNotification
from clients.gateway_client import ClientGatewayClient
from utils.geo import find_nearby_drivers
from repository.driver_repository import DriverRepository

logger = logging.getLogger(__name__)

class DriverNotificationService:
    """Сервіс для сповіщення водіїв з підтримкою БД (Task 1 & 2)"""
    
    def __init__(
        self,
        gateway_client: ClientGatewayClient,
        session_factory: sessionmaker,  # ВИПРАВЛЕНО: додано для роботи з БД
        max_retries: int = 3
    ):
        self.gateway_client = gateway_client
        self.session_factory = session_factory
        self.max_retries = max_retries
    
    async def send_trip_request_to_driver(
        self,
        driver_id: str,
        notification: TripRequestNotification
    ) -> bool:
        """Відправка запиту конкретному водію з оновленням статусу в БД"""
        async with self.session_factory() as session:
            repo = DriverRepository(session)
            driver = await repo.get_by_id(driver_id)
            
            if not driver:
                logger.error(f"Driver {driver_id} not found in DB")
                return False
            
            if driver.status not in ["AVAILABLE", "ONLINE"]:
                logger.warning(f"Driver {driver_id} is busy or offline (status: {driver.status})")
                return False

            # Логіка повторних спроб відправки через Gateway
            for attempt in range(1, self.max_retries + 1):
                try:
                    success = await self.gateway_client.send_driver_notification(
                        driver_id=str(driver.telegram_id), # Відправляємо на Telegram ID
                        notification=notification
                    )
                    
                    if success:
                        await repo.update_status(driver.id, "NOTIFIED")
                        return True
                    
                    logger.warning(f"Gateway retry {attempt}/{self.max_retries} for driver {driver_id}")
                except Exception as e:
                    logger.error(f"Error notifying driver {driver_id}: {e}")
            
            return False
    
    async def notify_nearby_drivers(
        self,
        trip_id: str,
        pickup_latitude: float,
        pickup_longitude: float,
        notification_data: dict,
        radius_km: float = 5.0
    ) -> List[str]:
        """Пошук водіїв у БД та їх масове сповіщення (Phase 2)"""
        async with self.session_factory() as session:
            repo = DriverRepository(session)
            # Отримуємо всіх потенційно вільних водіїв
            db_drivers = await repo.list_all(status="AVAILABLE")
            
            # Конвертуємо об'єкти БД у формат, який розуміє find_nearby_drivers
            drivers_map = {}
            for d in db_drivers:
                drivers_map[str(d.id)] = {
                    "id": str(d.id),
                    "status": d.status,
                    "location": f"{d.last_lat},{d.last_lon}"
                }

        # Використовуємо твою гео-утиліту
        nearby = find_nearby_drivers(
            drivers=drivers_map,
            pickup_lat=pickup_latitude,
            pickup_lng=pickup_longitude,
            radius_km=radius_km
        )
        
        notified_ids = []
        for d_info in nearby:
            notification = TripRequestNotification(
                trip_id=trip_id,
                driver_id=d_info["id"],
                **notification_data
            )
            if await self.send_trip_request_to_driver(d_info["id"], notification):
                notified_ids.append(d_info["id"])
                
        return notified_ids
