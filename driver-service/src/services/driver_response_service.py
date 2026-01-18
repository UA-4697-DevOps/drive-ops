import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import sessionmaker

from schemas.driver_response import (
    DriverResponseEvent,
    DriverAssignedPayload
)
from clients.rabbitmq_publisher import RabbitMQPublisher
from repository.driver_repository import DriverRepository

logger = logging.getLogger(__name__)

class DriverResponseService:
    """Service for processing driver accept/reject responses with DB persistence"""
    
    def __init__(
        self,
        publisher: RabbitMQPublisher,
        session_factory: sessionmaker
    ):
        self.publisher = publisher
        self.session_factory = session_factory

    async def _is_trip_handled_in_db(self, repo: DriverRepository, trip_id: str) -> bool:
        """
        Перевірка, чи замовлення вже має призначеного водія.
        Для MVP ми можемо додати таблицю trip_assignments або перевіряти статус.
        """
        # Логіка для перевірки стану поїздки в БД
        # Наразі ми покладаємось на статус водія та логи
        return False

    async def handle_driver_accept(
        self,
        repo: DriverRepository,
        driver_id: str,
        trip_id: str,
        timestamp: datetime
    ) -> bool:
        """Обробка прийняття поїздки водієм"""
        logger.info(f"Processing driver accept - Driver: {driver_id}, Trip: {trip_id}")
        
        # 1. Отримуємо дані водія
        driver = await repo.get_by_id(driver_id)
        if not driver:
            logger.error(f"Driver {driver_id} not found")
            return False

        # 2. Публікуємо подію для Trip Service (Go)
        # Це найважливіший крок для Phase 3
        payload = {
            "trip_id": trip_id,
            "driver_id": str(driver_id),
            "assigned_at": timestamp.isoformat()
        }
        
        success = await asyncio.to_thread(
            self.publisher.publish_event,
            event_type="trip.event.driver_assigned",
            payload=payload,
            routing_key="trip.event.driver_assigned"
        )
        
        if success:
            # 3. Оновлюємо статус водія в БД
            await repo.update_status(driver_id, "ON_TRIP")
            logger.info(f"✅ Event published and status updated for driver {driver_id}")
            return True
        
        return False

    async def handle_driver_reject(
        self,
        repo: DriverRepository,
        driver_id: str,
        trip_id: str
    ) -> bool:
        """Обробка відхилення замовлення"""
        logger.info(f"Driver {driver_id} rejected trip {trip_id}")
        # Повертаємо водія в статус доступного
        await repo.update_status(driver_id, "AVAILABLE")
        return True

    async def process_driver_response(self, event: DriverResponseEvent) -> bool:
        """Головний вхідний пункт для обробки подій з RabbitMQ"""
        payload = event.payload
        
        async with self.session_factory() as session:
            repo = DriverRepository(session)
            
            if payload.decision == "accept":
                return await self.handle_driver_accept(
                    repo, str(payload.driver_id), payload.trip_id, payload.timestamp
                )
            elif payload.decision == "reject":
                return await self.handle_driver_reject(
                    repo, str(payload.driver_id), payload.trip_id
                )
            
        return False
