import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import sessionmaker

from schemas.trip_request import TripRequestNotification
from clients.gateway_client import ClientGatewayClient
from utils.geo import find_nearby_drivers
from repository.driver_repository import DriverRepository

logger = logging.getLogger(__name__)

class DriverNotificationService:
    """Service for finding and notifying drivers via DB and Gateway"""
    
    def __init__(
        self,
        gateway_client: ClientGatewayClient,
        session_factory: sessionmaker,
        max_retries: int = 3
    ):
        self.gateway_client = gateway_client
        self.session_factory = session_factory
        self.max_retries = max_retries

    async def send_trip_request_to_driver(
        self,
        repo: DriverRepository,
        driver_id: str,
        notification: TripRequestNotification
    ) -> bool:
        """Відправка пуш-повідомлення в бот з повторними спробами"""
        driver = await repo.get_by_id(driver_id)
        if not driver or not driver.telegram_id:
            logger.error(f"Driver {driver_id} has no telegram_id")
            return False

        # Спроба відправки через Gateway Client
        for attempt in range(1, self.max_retries + 1):
            try:
                success = await self.gateway_client.send_driver_notification(
                    driver_id=driver.telegram_id,
                    notification=notification
                )
                if success:
                    await repo.update_status(driver.id, "NOTIFIED")
                    return True
            except Exception as e:
                logger.warning(f"Attempt {attempt} failed for driver {driver_id}: {e}")
        
        return False

    async def notify_nearby_drivers(
        self,
        trip_id: str,
        pickup_latitude: float,
        pickup_longitude: float,
        notification_data: dict,
        radius_km: float = 5.0
    ) -> List[str]:
        """Пошук водіїв поруч та відправка замовлень (Phase 2)"""
        async with self.session_factory() as session:
            repo = DriverRepository(session)
            # 1. Шукаємо всіх, хто потенційно вільний
            available_drivers = await repo.list_all(status="AVAILABLE")
            
            # Формуємо карту для алгоритму geo.py
            drivers_map = {
                str(d.id): {
                    "id": str(d.id),
                    "status": d.status,
                    "location": f"{d.last_lat},{d.last_lon}"
                } for d in available_drivers
            }

            # 2. Розраховуємо відстань
            nearby = find_nearby_drivers(
                drivers=drivers_map,
                pickup_lat=pickup_latitude,
                pickup_lng=pickup_longitude,
                radius_km=radius_km
            )
            
            if not nearby:
                logger.warning(f"No drivers near trip {trip_id}")
                return []

            # 3. Сповіщаємо знайдених водіїв
            notified_ids = []
            for d_info in nearby:
                notification = TripRequestNotification(
                    trip_id=trip_id,
                    driver_id=d_info["id"],
                    **notification_data
                )
                if await self.send_trip_request_to_driver(repo, d_info["id"], notification):
                    notified_ids.append(d_info["id"])
            
            return notified_ids
