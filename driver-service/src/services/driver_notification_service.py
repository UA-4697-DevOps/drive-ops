"""
Service for handling driver notifications and trip requests
Uses in-memory drivers storage until database is ready
"""
import logging
from typing import List, Dict, Any
from datetime import datetime

# [FIXED] Imported Location schema to satisfy TripRequestNotification requirements
from src.schemas.trip_request import TripRequestNotification, Location
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
        Processes trip payload and triggers geo-fenced notifications.
        [FIXED] Updated to use camelCase (tripId) and Location objects for schema compliance.
        """
        # [FIXED] Synchronized with Go service output (camelCase)
        trip_id = trip_payload.get('tripId')
        pickup_data = trip_payload.get('pickup', {})
        dropoff_data = trip_payload.get('dropoff', {})
        
        # Coordinates for geo-fencing
        lat = pickup_data.get('lat', 50.4501)
        lng = pickup_data.get('lng', 30.5234)

        logger.info(f"SQS Event: Processing driver discovery for Trip {trip_id}")

        # [FIXED] Construct Location objects to satisfy Pydantic schema
        notification_data = {
            "pickup": Location(
                lat=lat,
                lng=lng,
                address=pickup_data.get('address', 'Unknown')
            ),
            "dropoff": Location(
                lat=dropoff_data.get('lat', 0.0),
                lng=dropoff_data.get('lng', 0.0),
                address=dropoff_data.get('address', 'Unknown')
            ),
            # [FIXED] Use UTC for cross-service consistency
            "created_at": datetime.utcnow()
        }

        # Bridge to the existing geo-fencing logic
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
        
        status = driver.get("status", "OFFLINE")
        if status not in ["AVAILABLE", "ONLINE"]:
            logger.warning(f"Driver {driver_id} is {status}, skipping.")
            return False
        
        for attempt in range(1, self.max_retries + 1):
            try:
                success = await self.gateway_client.send_driver_notification(
                    driver_id=driver_id,
                    notification=notification
                )
                
                if success:
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
            
            # [FIXED] Pydantic will now validate correctly because notification_data 
            # keys match the Location fields exactly
            notification = TripRequestNotification(
                trip_id=trip_id,
                driver_id=driver_id,
                **notification_data
            )
            
            if await self.send_trip_request_to_driver(driver_id, notification):
                notified_drivers.append(driver_id)
        
        return notified_drivers
