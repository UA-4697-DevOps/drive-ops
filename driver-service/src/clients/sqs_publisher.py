import boto3
import json
import uuid
import logging
from src.config import settings

logger = logging.getLogger(__name__)

class SQSPublisher:
    def __init__(self):
        try:
            self.sqs = boto3.client(
                "sqs",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                endpoint_url=settings.SQS_ENDPOINT_URL,
            )
            self.queue_url = settings.SQS_DRIVER_ASSIGNED_URL
            logger.info(f"Initialized SQSPublisher for queue: {self.queue_url}")
        except Exception as e:
            logger.error(f"Failed to initialize SQS client: {e}")
            raise e

    def publish_driver_assigned(self, trip_id: str, driver_id: str, driver_name: str, vehicle_info: dict) -> bool:
        """
        Publishes the driver.assigned event to SQS matching the schema 
        expected by TripService (Go).
        """
        payload = {
            "tripId": str(trip_id),
            "driverId": str(driver_id),
            "driverName": driver_name,
            "vehicleInfo": vehicle_info
        }

        # Envelope matching the Go Consumer expectation
        message_body = {
            "version": "1.0",
            "messageId": str(uuid.uuid4()),
            "eventType": "driver.assigned",
            "payload": payload
        }

        try:
            response = self.sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body)
            )
            logger.info(f"Published SQS event driver.assigned for Trip {trip_id}. MessageId: {response.get('MessageId')}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish SQS message for Trip {trip_id}: {e}")
            return False
