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
            # [FIX] Fully removed SQS_ENDPOINT logic
            self.sqs = boto3.client(
                "sqs",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            
            self.assigned_queue_url = settings.SQS_DRIVER_ASSIGNED_URL
            self.completed_queue_url = settings.SQS_TRIP_COMPLETED_URL
            
            logger.info("Initialized SQSPublisher for real AWS (Production Mode).")
            
        except Exception as e:
            logger.error(f"Failed to initialize SQS client: {e}")
            raise e

    def publish_driver_assigned(self, trip_id: str, driver_id: str, driver_name: str, vehicle_info: dict) -> bool:
        """
        Publishes the driver.assigned event.
        [FIX] Keys updated to camelCase to match Go TripService SQSMessageEnvelope and Payload tags.
        """
        now_iso = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        correlation_id = f"trip-{trip_id}" 

        # Payload keys updated to camelCase for Go compatibility
        payload = {
            "tripId": str(trip_id),
            "driverId": str(driver_id),
            "driverName": driver_name,
            "vehicleInfo": vehicle_info,
            "assignedAt": now_iso
        }

        # Envelope keys updated to camelCase
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
            self.sqs.send_message(
                QueueUrl=self.assigned_queue_url,
                MessageBody=json.dumps(message_body),
                MessageGroupId=correlation_id,
                MessageDeduplicationId=f"assign_{trip_id}_{driver_id}"
            )
            logger.info(f"Published driver.assigned for Trip {trip_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish driver.assigned: {e}")
            return False

    def publish_trip_completed(self, trip_id: str, driver_id: str, timestamp: datetime = None) -> bool:
        """
        Publishes the trip.completed event.
        [FIX] All keys (Envelope and Payload) synchronized to camelCase.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        elif timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
            
        now_iso = timestamp.isoformat().replace('+00:00', 'Z')
        correlation_id = f"trip-{trip_id}"

        # Payload keys updated to camelCase (Matches Go's TripCompletedPayload struct)
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
            self.sqs.send_message(
                QueueUrl=self.completed_queue_url,
                MessageBody=json.dumps(message_body),
                MessageGroupId=correlation_id,
                MessageDeduplicationId=f"complete_{trip_id}"
            )
            logger.info(f"Published trip.completed for Trip {trip_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish trip.completed: {e}")
            return False
