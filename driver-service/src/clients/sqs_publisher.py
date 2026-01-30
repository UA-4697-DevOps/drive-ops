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
                endpoint_url=boto_endpoint, 
            )
            
            # [UPDATED] Load specific queue URLs from settings
            self.assigned_queue_url = settings.SQS_DRIVER_ASSIGNED_URL
            self.completed_queue_url = settings.SQS_TRIP_COMPLETED_URL
            
            logger.info(
                f"Initialized SQSPublisher. Assigned Queue: {self.assigned_queue_url}, "
                f"Completed Queue: {self.completed_queue_url}"
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize SQS client: {e}")
            raise e

    def publish_driver_assigned(self, trip_id: str, driver_id: str, driver_name: str, vehicle_info: dict) -> bool:
        """
        Publishes the driver.assigned event to SQS matching the STRICT schema 
        expected by TripService (Go).
        """
        #
        now_iso = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        correlation_id = f"trip-{trip_id}" 

        payload = {
            "tripId": str(trip_id),
            "driverId": str(driver_id),
            "driverName": driver_name,
            "vehicleInfo": vehicle_info,
            "assignedAt": now_iso
        }

        # MessageDeduplicationId must be a stable idempotency key.
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
            if not self.assigned_queue_url:
                raise ValueError("SQS_DRIVER_ASSIGNED_URL is not configured")
            
            self.sqs.send_message(
                QueueUrl=self.assigned_queue_url,
                MessageBody=json.dumps(message_body),
                MessageGroupId=correlation_id, # Ensures per-trip ordering
                MessageDeduplicationId=deduplication_id
            )
            logger.info(f"Published SQS event driver.assigned for Trip {trip_id}. CorrelationID: {correlation_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish driver.assigned for Trip {trip_id}: {e}")
            return False

    def publish_trip_completed(self, trip_id: str, driver_id: str, timestamp: datetime = None) -> bool:
        """
        Publishes the trip.completed event to SQS matching the design document schema.
        """
        # 1. Handle timestamp and timezone-naive input
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        elif timestamp.tzinfo is None:
            # Treat naive datetime as UTC
            timestamp = timestamp.replace(tzinfo=timezone.utc)
            
        now_iso = timestamp.isoformat().replace('+00:00', 'Z')
        correlation_id = f"trip-{trip_id}"

        payload = {
            "tripId": str(trip_id),
            "driverId": str(driver_id),
            "completedAt": now_iso,
            "status": "COMPLETED"
        }

        message_body = {
            "version": "1.0",
            "messageId": str(uuid.uuid4()),
            "timestamp": now_iso,
            "correlationId": correlation_id,
            "eventType": "trip.completed",
            "source": "driver-service",
            "payload": payload
        }

        try:
            if not self.completed_queue_url:
                raise ValueError("SQS_TRIP_COMPLETED_URL is not configured")

            self.sqs.send_message(
                QueueUrl=self.completed_queue_url,
                MessageBody=json.dumps(message_body),
                MessageGroupId=correlation_id, # Ensures order: assigned -> completed
                MessageDeduplicationId=f"complete_{trip_id}" # Prevents double completion
            )
            logger.info(f"Published SQS event trip.completed for Trip {trip_id}. CorrelationID: {correlation_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish trip.completed for Trip {trip_id}: {e}")
            return False
