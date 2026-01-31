"""
Service for handling driver notifications and trip requests
Uses in-memory drivers storage until database is ready
"""
import logging
from typing import List, Dict, Any
from datetime import datetime

from src.schemas.trip_request import TripRequestNotification
from src.clients.gateway_client import ClientGatewayClient
from src.utils.geo import find_nearby_drivers

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

    async def notify_available_drivers(self, trip_payload: dict):
        """
        [FIXED] Entry point for SQS Consumer. 
        Parses raw SQS payload and triggers the nearby driver search.
        Updated to use snake_case keys (trip_id) to match Go service output.
        """
        # Match Go's JSON tags (snake_case)
        trip_id = trip_payload.get('trip_id')
        pickup = trip_payload.get('pickup', {})
        
        # Extract coordinates with Kyiv defaults
        lat = pickup.get('lat', 50.4501)
        lng = pickup.get('lng', 30.5234)

        logger.info(f"SQS Event: Processing driver discovery for Trip {trip_id}")

        # Prepare data for the notification schema
        notification_data = {
            "pickup_address": pickup.get('address', 'Unknown'),
            "dropoff_address": trip_payload.get('dropoff', {}).get('address', 'Unknown'),
            "created_at": datetime.now() # Fallback timestamp
        }

        # Bridge to the existing geo-fencing logic
        # Ensure trip_id is a string for consistent dictionary mapping
        return await self.notify_nearby_drivers(
            trip_id=str(trip_id),
            pickup_latitude=lat,
            pickup_longitude=lng,
            notification_data=notification_data
        )
    
    async def send_trip_request_to_driver(
        self,
        driver_id: str,
        notification: TripRequestNotification
    ) -> bool:
        """Send trip request to specific driver with retry logic"""
        logger.info(f"Attempting notification: Trip {notification.trip_id} -> Driver {driver_id}")
        
        driver = self.drivers.get(driver_id)
        if not driver:
            logger.error(f"Driver not found in memory: {driver_id}")
            return False
        
        # Support both 'AVAILABLE' (legacy) and 'ONLINE' (new status)
        status = driver.get("status", "OFFLINE")
        if status not in ["AVAILABLE", "ONLINE"]:
            logger.warning(f"Driver {driver_id} is {status}, skipping.")
            return False
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # Dispatches to Telegram via Gateway
                success = await self.gateway_client.send_driver_notification(
                    driver_id=driver_id,
                    notification=notification
                )
                
                if success:
                    # Update status so we don't spam the same driver
                    driver["status"] = "NOTIFIED"
                    return True
                
            except Exception as e:
                logger.error(f"Attempt {attempt} failed for driver {driver_id}: {e}")
        
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
        nearby_drivers = find_nearby_drivers(
            drivers=self.drivers,
            pickup_lat=pickup_latitude,
            pickup_lng=pickup_longitude,
            radius_km=radius_km,
            max_drivers=10
        )
        
        if not nearby_drivers:
            logger.warning(f"No available drivers in {radius_km}km radius for trip {trip_id}")
            return []
        
        notified_drivers = []
        for driver in nearby_drivers:
            driver_id = driver["id"]
            
            notification = TripRequestNotification(
                trip_id=trip_id,
                driver_id=driver_id,
                **notification_data
            )
            
            if await self.send_trip_request_to_driver(driver_id, notification):
                notified_drivers.append(driver_id)
        
        return notified_drivers
