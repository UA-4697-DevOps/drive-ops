"""
Service for handling driver responses (accept/reject) to trip requests
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from src.schemas.driver_response import DriverResponseEvent
# We keep DriverResponseEvent for the input, but we don't need DriverAssignedPayload
# because the SQS Publisher now handles the outgoing data structure.

from src.clients.sqs_publisher import SQSPublisher

logger = logging.getLogger(__name__)


class DriverResponseService:
    """Service for processing driver accept/reject responses"""
    
    def __init__(
        self,
        publisher: SQSPublisher,
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
        """
        # Check if driver exists
        if driver_id not in self.drivers:
            return False, f"Driver {driver_id} not found"
        
        # Check if trip request exists
        if trip_id not in self.trip_requests:
            return False, f"Trip request {trip_id} not found"
        
        return True, None
    
    async def handle_driver_accept(
        self,
        driver_id: str,
        trip_id: str,
        timestamp: datetime
    ) -> bool:
        """
        Handle driver accepting trip request
        """
        logger.info(
            f"Processing driver accept - Driver: {driver_id}, Trip: {trip_id}"
        )
        
        # 1. Validate response (existence only)
        is_valid, error_msg = self._validate_response(driver_id, trip_id)
        if not is_valid:
            logger.error(
                f"Invalid accept response - Driver: {driver_id}, "
                f"Trip: {trip_id}, Error: {error_msg}"
            )
            return False  # Genuine error - will retry
        
        # 2. Handle idempotent cases as success (no retry)
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
        
        # --- Prepare Data for SQS ---
        driver_data = self.drivers.get(driver_id, {})
        
        vehicle_info = {
            "make": driver_data.get("vehicle_make", "Unknown"),
            "model": driver_data.get("vehicle_model", "Unknown"),
            "licensePlate": driver_data.get("license_plate", "UNKNOWN")
        }
        driver_name = driver_data.get("name", "Unknown Driver")
        
        # 3. Publish event FIRST before updating state
        # We pass raw data to SQSPublisher, which handles formatting
        success = await asyncio.to_thread(
            self.publisher.publish_driver_assigned,
            trip_id=trip_id,
            driver_id=driver_id,
            driver_name=driver_name,
            vehicle_info=vehicle_info
        )
        
        if not success:
            logger.error(
                f"Failed to publish driver_assigned event - "
                f"Driver: {driver_id}, Trip: {trip_id}"
            )
            return False  # Will retry
        
        # 4. Only update state AFTER successful publish
        trip_data = self.trip_requests[trip_id]
        trip_data["status"] = "assigned"
        trip_data["assigned_driver_id"] = driver_id
        trip_data["assigned_at"] = timestamp
        
        # Record response
        if "responses" not in trip_data:
            trip_data["responses"] = {}
        trip_data["responses"][driver_id] = "accept"
        
        # Update driver status
        if driver_id in self.drivers:
            self.drivers[driver_id]["status"] = "ON_TRIP"
            logger.info(f"Driver {driver_id} status updated to ON_TRIP locally")
        
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
        Handle driver rejecting trip request.
        Updates local state and releases driver back to AVAILABLE status.
        """
        logger.info(
            f"Processing driver reject - Driver: {driver_id}, Trip: {trip_id}"
        )
        
        # 1. Validate response existence
        is_valid, error_msg = self._validate_response(driver_id, trip_id)
        if not is_valid:
            logger.error(
                f"Invalid reject response - Driver: {driver_id}, "
                f"Trip: {trip_id}, Error: {error_msg}"
            )
            return False  # Genuine error - will retry
        
        # 2. Handle idempotent cases
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
        
        # 3. Update local trip request state
        trip_data = self.trip_requests[trip_id]
        
        # Record the rejection response
        if "responses" not in trip_data:
            trip_data["responses"] = {}
        trip_data["responses"][driver_id] = "reject"
        
        # 4. Update driver status back to AVAILABLE so they can receive other orders
        driver = self.drivers.get(driver_id)
        if driver:
            driver["status"] = "AVAILABLE"
        
        logger.info(
            f"Driver rejection recorded - Driver: {driver_id}, Trip: {trip_id}"
        )
        
        # NOTE: For MVP, we just log the rejection. 
        # Future Phase: Implement matching logic to notify the next nearest driver.
        return True
    
    async def handle_trip_completion(
        self,
        driver_id: str,
        trip_id: str,
        timestamp: datetime
    ) -> bool:
        """
        Processes trip completion and publishes event to SQS.
        Includes ownership and state validation guards.
        """
        logger.info(f"Processing trip completion - Driver: {driver_id}, Trip: {trip_id}")

        # 1. Validate basic existence
        is_valid, error_msg = self._validate_response(driver_id, trip_id)
        if not is_valid:
            logger.error(f"Invalid completion - Error: {error_msg}")
            return False

        # 2. Security & State Guard: Ensure the trip is active and owned by this driver
        trip_data = self.trip_requests.get(trip_id)
        
        # Check status: must be 'assigned' (Active)
        if trip_data.get("status") != "assigned":
            logger.info(
                f"Trip {trip_id} completion ignored: status is '{trip_data.get('status')}', "
                f"expected 'assigned' (idempotent check)."
            )
            return True  # Successfully ignored

        # Check Ownership: Compare as strings to prevent UUID object mismatches
        if str(trip_data.get("assigned_driver_id")) != str(driver_id):
            logger.error(
                f"UNAUTHORIZED: Driver {driver_id} tried to complete trip {trip_id} "
                f"assigned to {trip_data.get('assigned_driver_id')}"
            )
            return False

        # 3. Prepare payload and publish to SQS via thread pool
        success = await asyncio.to_thread(
            self.publisher.publish_trip_completed,
            trip_id=trip_id,
            driver_id=driver_id,
            timestamp=timestamp
        )

        if not success:
            logger.error(f"Failed to publish trip_completed event for trip {trip_id}")
            return False

        # 4. Finalize local state update
        trip_data["status"] = "completed"
        trip_data["completed_at"] = timestamp
        
        # 5. Set driver back to ONLINE (Available) for new orders
        if driver_id in self.drivers:
            self.drivers[driver_id]["status"] = "ONLINE"
            logger.info(f"Driver {driver_id} status updated to ONLINE locally after completion")

        return True

    async def process_driver_response(self, event: DriverResponseEvent) -> bool:
        """
        Main router for driver response events (accept or reject).
        Used by the background RabbitMQ/SQS consumer.
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
