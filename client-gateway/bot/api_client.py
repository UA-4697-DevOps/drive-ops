import os
import httpx
import time
from .logger_utils import create_trip_request_logger, generate_correlation_id

logger = create_trip_request_logger()

TRIP_SERVICE_URL = os.getenv('TRIP_SERVICE_URL', 'http://trip-service:8081')
DRIVER_SERVICE_URL = os.getenv('DRIVER_SERVICE_URL', 'http://driver-service:8082')

class APIClient:
    @staticmethod
    async def _request(method, url, **kwargs):
        correlation_id = generate_correlation_id()
        start_time = time.time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.request(method, url, **kwargs)
                latency = int((time.time() - start_time) * 1000)
                logger.info(f"{method} {url} | Status: {resp.status_code} | {latency}ms", extra={'correlationId': correlation_id})
                
                if resp.status_code in (200, 201, 204):
                    return {'success': True, 'data': resp.json() if resp.text else {}}
                return {'success': False, 'error': {'status_code': resp.status_code, 'message': resp.text}}
            except Exception as e:
                logger.error(f"API Error: {str(e)}", extra={'correlationId': correlation_id})
                return {'success': False, 'error': {'status_code': 500, 'message': str(e)}}

    @classmethod
    async def create_trip(cls, payload):
        return await cls._request("POST", f"{TRIP_SERVICE_URL}/trips", json=payload)

    @classmethod
    async def get_trip_status(cls, trip_id):
        return await cls._request("GET", f"{TRIP_SERVICE_URL}/trips/{trip_id}")

    @classmethod
    async def register_driver(cls, payload):
        return await cls._request("POST", f"{DRIVER_SERVICE_URL}/drivers", json=payload)

    @classmethod
    async def update_driver_status(cls, driver_id, status):
        return await cls._request("POST", f"{DRIVER_SERVICE_URL}/drivers/{driver_id}/status", params={'status': status.upper()})

    @classmethod
    async def respond_to_trip(cls, driver_id, trip_id, action):
        return await cls._request("POST", f"{DRIVER_SERVICE_URL}/drivers/{driver_id}/trips/{trip_id}/{action}")
    @classmethod
    async def fetch_driver_trips(cls, driver_id):
        """Отримання активних поїздок водія"""
        return await cls._request("GET", f"{DRIVER_SERVICE_URL}/drivers/{driver_id}/trips")

    @classmethod
    async def finish_trip(cls, driver_id, trip_id):
        """Завершення поїздки"""
        return await cls._request("POST", f"{DRIVER_SERVICE_URL}/drivers/{driver_id}/trips/{trip_id}/complete")
