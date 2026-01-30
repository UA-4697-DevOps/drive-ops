import boto3
import json
import uuid
import logging
from datetime import datetime, timezone
from src.config import settings

logger = logging.getLogger(__name__)

class SQSPublisher:
    def __init__(self):
        try:
            # Defensive check for empty or whitespace-only endpoint strings
            boto_endpoint = settings.SQS_ENDPOINT if settings.SQS_ENDPOINT and settings.SQS_ENDPOINT.strip() else None
            
            self.sqs = boto3.client(
                "sqs",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                endpoint_url=boto_endpoint, # Use the sanitized variable
            )
            self.queue_url = settings.SQS_DRIVER_ASSIGNED_URL
            
            log_msg = f"Initialized SQSPublisher for queue: {self.queue_url}"
            if boto_endpoint:
                log_msg += f" (Custom Endpoint: {boto_endpoint})"
            logger.info(log_msg)
            
        except Exception as e:
            logger.error(f"Failed to initialize SQS client: {e}")
            raise e

    def publish_driver_assigned(self, trip_id: str, driver_id: str, driver_name: str, vehicle_info: dict) -> bool:
        """
        Publishes the driver.assigned event to SQS matching the STRICT schema 
        expected by TripService (Go).
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        correlation_id = str(uuid.uuid4()) 

        payload = {
            "tripId": str(trip_id),
            "driverId": str(driver_id),
            "driverName": driver_name,
            "vehicleInfo": vehicle_info,
            "assignedAt": now_iso
        }

        # [FIXED] MessageDeduplicationId must be a stable idempotency key.
        # A random UUID (like in messageId) defeats deduplication.
        # We use a combination of business IDs to ensure retries are ignored by AWS SQS FIFO.
        deduplication_id = f"assign_{trip_id}_{driver_id}"

        message_body = {
            "version": "1.0",
            "messageId": str(uuid.uuid4()),
            "correlationId": correlation_id,
            "eventType": "driver.assigned",
            "source": "driver-service",
            "timestamp": now_iso,
            "payload": payload
        }

        try:
            if not self.queue_url:
                raise ValueError("SQS_DRIVER_ASSIGNED_URL is not configured")
            
            response = self.sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body),
                MessageGroupId=str(trip_id), # Groups messages by trip to maintain order per trip
                MessageDeduplicationId=deduplication_id # [FIXED] Stable ID for idempotency
            )
            logger.info(f"Published SQS event driver.assigned for Trip {trip_id}. CorrelationID: {correlation_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish SQS message for Trip {trip_id}: {e}")
            return False
