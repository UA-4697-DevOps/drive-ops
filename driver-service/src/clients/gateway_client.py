"""
HTTP client for communicating with Client Gateway
"""
import httpx
import logging
from src.schemas.trip_request import TripRequestNotification

logger = logging.getLogger(__name__)


class ClientGatewayClient:
    """HTTP client for communicating with Client Gateway"""
    
    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def send_driver_notification(
        self,
        driver_id: str,
        notification: TripRequestNotification
    ) -> bool:
        """Send push notification to driver via Client Gateway"""
        url = f"{self.base_url}/api/v1/notifications/driver/{driver_id}"
        
        payload = {
            "type": "trip_request",
            "data": notification.model_dump(mode='json')
        }
        
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            
            logger.info(
                f"Successfully sent notification to driver - "
                f"Driver ID: {driver_id}, Trip ID: {notification.trip_id}"
            )
            return True
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error sending notification to driver {driver_id}: "
                f"Status {e.response.status_code}, Trip ID: {notification.trip_id}"
            )
            return False
            
        except httpx.RequestError as e:
            logger.error(
                f"Request error sending notification to driver {driver_id}: {e}, "
                f"Trip ID: {notification.trip_id}"
            )
            return False
        
        except Exception as e:
            logger.error(
                f"Unexpected error sending notification to driver {driver_id}: {e}"
            )
            return False
    
    async def close(self):
        """Close HTTP client connection"""
        await self.client.aclose()
