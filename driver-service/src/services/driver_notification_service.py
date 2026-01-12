"""
Service for handling driver notifications and trip requests
Uses in-memory drivers storage until database is ready
"""
import logging
from typing import List, Dict, Any

from schemas.trip_request import TripRequestNotification
from clients.gateway_client import ClientGatewayClient
from utils.geo import find_nearby_drivers

logger = logging.getLogger(__name__)


class DriverNotificationService:
    """Service for handling driver notifications and trip requests"""
    
    def __init__(
        self,
        gateway_client: ClientGatewayClient,
        drivers_storage: Dict[str, Dict[str, Any]],
        max_retries: int = 3
    ):
        self.gateway_client = gateway_client
        self.drivers = drivers_storage
        self.max_retries = max_retries
    
    async def send_trip_request_to_driver(
        self,
        driver_id: str,
        notification: TripRequestNotification
    ) -> bool:
        """Send trip request to specific driver with retry logic"""
        logger.info(
            f"Attempting to send trip request - "
            f"Trip ID: {notification.trip_id}, Driver ID: {driver_id}"
        )
        
        # Verify driver exists
        driver = self.drivers.get(driver_id)
        if not driver:
            logger.error(f"Driver not found: {driver_id}")
            return False
        
        # Check if driver is available
        status = driver.get("status", "OFFLINE")
        if status not in ["AVAILABLE", "ONLINE"]:
            logger.warning(
                f"Driver {driver_id} is not available (status: {status})"
            )
            return False
        
        # Retry logic
        for attempt in range(1, self.max_retries + 1):
            try:
                success = await self.gateway_client.send_driver_notification(
                    driver_id=driver_id,
                    notification=notification
                )
                
                if success:
                    logger.info(
                        f"Successfully dispatched trip request - "
                        f"Trip ID: {notification.trip_id}, Driver ID: {driver_id}"
                    )
                    
                    # Update driver status to NOTIFIED
                    driver["status"] = "NOTIFIED"
                    return True
                else:
                    logger.warning(
                        f"Failed to dispatch trip request "
                        f"(attempt {attempt}/{self.max_retries}) - "
                        f"Trip ID: {notification.trip_id}, Driver ID: {driver_id}"
                    )
                    
            except Exception as e:
                logger.error(
                    f"Error sending trip request "
                    f"(attempt {attempt}/{self.max_retries}): {e} - "
                    f"Trip ID: {notification.trip_id}, Driver ID: {driver_id}"
                )
        
        # All retries failed
        logger.error(
            f"Failed to dispatch trip request after {self.max_retries} attempts - "
            f"Trip ID: {notification.trip_id}, Driver ID: {driver_id}"
        )
        return False
    
    async def notify_nearby_drivers(
        self,
        trip_id: str,
        pickup_latitude: float,
        pickup_longitude: float,
        notification_data: dict,
        radius_km: float = 5.0
    ) -> List[str]:
        """Find and notify nearby available drivers"""
        # Find nearby available drivers
        nearby_drivers = find_nearby_drivers(
            drivers=self.drivers,
            pickup_lat=pickup_latitude,
            pickup_lon=pickup_longitude,
            radius_km=radius_km,
            max_drivers=10
        )
        
        if not nearby_drivers:
            logger.warning(f"No available drivers found for trip {trip_id}")
            return []
        
        logger.info(
            f"Found {len(nearby_drivers)} nearby drivers for trip {trip_id}"
        )
        
        notified_drivers = []
        
        # Send notifications to all nearby drivers
        for driver in nearby_drivers:
            driver_id = driver["id"]
            
            notification = TripRequestNotification(
                trip_id=trip_id,
                driver_id=driver_id,
                **notification_data
            )
            
            success = await self.send_trip_request_to_driver(
                driver_id=driver_id,
                notification=notification
            )
            
            if success:
                notified_drivers.append(driver_id)
        
        logger.info(
            f"Successfully notified {len(notified_drivers)}/{len(nearby_drivers)} "
            f"drivers for trip {trip_id}: {notified_drivers}"
        )
        
        return notified_drivers
