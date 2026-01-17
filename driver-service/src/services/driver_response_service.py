"""
Service for handling driver responses (accept/reject) to trip requests
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from schemas.driver_response import (
    DriverResponseEvent,
    DriverAssignedPayload
)
from clients.rabbitmq_publisher import RabbitMQPublisher

logger = logging.getLogger(__name__)


class DriverResponseService:
    """Service for processing driver accept/reject responses"""
    
    def __init__(
        self,
        publisher: RabbitMQPublisher,
        drivers_storage: Dict[str, Dict[str, Any]],
        trip_requests_storage: Dict[str, Dict[str, Any]]
    ):
        self.publisher = publisher
        self.drivers = drivers_storage
        self.trip_requests = trip_requests_storage
    
    def _is_duplicate_response(self, trip_id: str, driver_id: str) -> bool:
        """Check if driver already responded to this trip (idempotency check)"""
        trip_data = self.trip_requests.get(trip_id)
        if not trip_data:
            return False
        
        responses = trip_data.get("responses", {})
        return driver_id in responses
    
    def _is_trip_already_assigned(self, trip_id: str) -> bool:
        """Check if trip is already assigned to another driver"""
        trip_data = self.trip_requests.get(trip_id)
        if not trip_data:
            return False
        
        return trip_data.get("status") == "assigned"
    
    def _validate_response(
        self,
        driver_id: str,
        trip_id: str
    ) -> tuple[bool, Optional[str]]:
        """
        Validate driver response (only checks existence, not idempotency)
        
        Returns:
            (is_valid, error_message)
        """
        # Check if driver exists
        if driver_id not in self.drivers:
            return False, f"Driver {driver_id} not found"
        
        # Check if trip request exists
        if trip_id not in self.trip_requests:
            return False, f"Trip request {trip_id} not found"
        
        # FIXED: Don't check duplicates here - handle as success in handlers
        return True, None
    
    async def handle_driver_accept(
        self,
        driver_id: str,
        trip_id: str,
        timestamp: datetime
    ) -> bool:
        """
        Handle driver accepting trip request
        
        Returns:
            True if processed successfully (including idempotent cases), False otherwise
        """
        logger.info(
            f"Processing driver accept - Driver: {driver_id}, Trip: {trip_id}"
        )
        
        # Validate response (existence only)
        is_valid, error_msg = self._validate_response(driver_id, trip_id)
        if not is_valid:
            logger.error(
                f"Invalid accept response - Driver: {driver_id}, "
                f"Trip: {trip_id}, Error: {error_msg}"
            )
            return False  # Genuine error - will retry
        
        # FIXED: Handle idempotent cases as success (no retry)
        if self._is_duplicate_response(trip_id, driver_id):
            logger.info(
                f"Duplicate accept ignored (idempotent) - Driver: {driver_id}, Trip: {trip_id}"
            )
            return True  # ACK without processing
        
        if self._is_trip_already_assigned(trip_id):
            logger.info(
                f"Accept ignored; trip already assigned - Driver: {driver_id}, Trip: {trip_id}"
            )
            return True  # ACK without processing
        
        # Publish event FIRST before updating state
        payload = DriverAssignedPayload(
            trip_id=trip_id,
            driver_id=driver_id,
            assigned_at=timestamp
        )
        
        # Use asyncio.to_thread to avoid blocking event loop
        success = await asyncio.to_thread(
            self.publisher.publish_event,
            event_type="trip.event.driver_assigned",
            payload=payload.model_dump(mode='json'),
            routing_key="trip.event.driver_assigned"
        )
        
        if not success:
            logger.error(
                f"Failed to publish driver_assigned event - "
                f"Driver: {driver_id}, Trip: {trip_id}"
            )
            return False  # Will retry
        
        # Only update state AFTER successful publish
        trip_data = self.trip_requests[trip_id]
        trip_data["status"] = "assigned"
        trip_data["assigned_driver_id"] = driver_id
        trip_data["assigned_at"] = timestamp
        
        # Record response
        if "responses" not in trip_data:
            trip_data["responses"] = {}
        trip_data["responses"][driver_id] = "accept"
        
        # Update driver status
        driver = self.drivers.get(driver_id)
        if driver:
            driver["status"] = "ON_TRIP"
        
        logger.info(
            f"Successfully processed driver accept and published assignment - "
            f"Driver: {driver_id}, Trip: {trip_id}"
        )
        
        return True
    
    async def handle_driver_reject(
        self,
        driver_id: str,
        trip_id: str,
        timestamp: datetime
    ) -> bool:
        """
        Handle driver rejecting trip request
        
        Returns:
            True if processed successfully (including idempotent cases), False otherwise
        """
        logger.info(
            f"Processing driver reject - Driver: {driver_id}, Trip: {trip_id}"
        )
        
        # Validate response (existence only)
        is_valid, error_msg = self._validate_response(driver_id, trip_id)
        if not is_valid:
            logger.error(
                f"Invalid reject response - Driver: {driver_id}, "
                f"Trip: {trip_id}, Error: {error_msg}"
            )
            return False  # Genuine error - will retry
        
        # FIXED: Handle idempotent cases as success (no retry)
        if self._is_duplicate_response(trip_id, driver_id):
            logger.info(
                f"Duplicate reject ignored (idempotent) - Driver: {driver_id}, Trip: {trip_id}"
            )
            return True  # ACK without processing
        
        if self._is_trip_already_assigned(trip_id):
            logger.info(
                f"Reject ignored; trip already assigned - Driver: {driver_id}, Trip: {trip_id}"
            )
            return True  # ACK without processing
        
        # Update trip request state
        trip_data = self.trip_requests[trip_id]
        
        # Record response
        if "responses" not in trip_data:
            trip_data["responses"] = {}
        trip_data["responses"][driver_id] = "reject"
        
        # Update driver status back to AVAILABLE
        driver = self.drivers.get(driver_id)
        if driver:
            driver["status"] = "AVAILABLE"
        
        logger.info(
            f"Driver rejection recorded - Driver: {driver_id}, Trip: {trip_id}"
        )
        
        # MVP: Just log rejection
        logger.warning(
            f"Trip {trip_id} rejected by driver {driver_id}. "
            f"Follow-up logic not yet implemented (MVP choice)."
        )
        
        return True
    
    async def process_driver_response(self, event: DriverResponseEvent) -> bool:
        """
        Process driver response event (accept or reject)
        
        Returns:
            True if processed successfully, False otherwise
        """
        payload = event.payload
        driver_id = payload.driver_id
        trip_id = payload.trip_id
        decision = payload.decision
        timestamp = payload.timestamp
        
        logger.info(
            f"Received driver response - "
            f"Driver: {driver_id}, Trip: {trip_id}, Decision: {decision}"
        )
        
        if decision == "accept":
            return await self.handle_driver_accept(driver_id, trip_id, timestamp)
        elif decision == "reject":
            return await self.handle_driver_reject(driver_id, trip_id, timestamp)
        else:
            logger.error(f"Unknown decision type: {decision}")
            return False
