import boto3
import json
import logging
import asyncio
from src.config import settings

logger = logging.getLogger(__name__)

class TripSQSConsumer:
    def __init__(self, notification_service, trip_requests_storage):
        self.notification_service = notification_service
        self.trip_requests = trip_requests_storage
        
        # SQS Client initialization
        self.sqs = boto3.client(
            "sqs",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.queue_url = settings.SQS_TRIP_CREATED_URL
        self.running = False

    async def start(self):
        """Starts the SQS long-polling loop for new trips"""
        self.running = True
        logger.info(f"Started Trip SQS Consumer polling: {self.queue_url}")
        
        while self.running:
            try:
                response = await asyncio.to_thread(
                    self.sqs.receive_message,
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=5,
                    WaitTimeSeconds=10, 
                    AttributeNames=['All']
                )

                messages = response.get('Messages', [])
                if not messages:
                    continue

                for msg in messages:
                    # [FIXED] Updated to call the internal _process_message method
                    await self._process_message(msg)

            except Exception as e:
                # [FIXED] Prevent tight loops if AWS is unreachable
                logger.error(f"Critical error in Trip SQS polling loop: {e}")
                await asyncio.sleep(5) 

    async def _process_message(self, message):
        receipt_handle = message['ReceiptHandle']
        try:
            body = json.loads(message['Body'])
            payload = body.get('payload', {})
            trip_id = payload.get('tripId')  # Matching camelCase sync

            if not trip_id:
                logger.error(f"Missing tripId in SQS payload. Keys: {list(payload.keys())}")
                # [FIXED] Delete incomplete message to prevent FIFO group blocking
                await self._delete_from_queue(receipt_handle)
                return

            # --- LOGIC INTEGRATION ---
            trip_id_str = str(trip_id)
            self.trip_requests[trip_id_str] = {
                "status": "pending",
                "pickup": payload.get('pickup'),
                "dropoff": payload.get('dropoff'),
                "created_at": body.get('timestamp'),
                "notified_drivers": [],
                "responses": {}
            }

            await self.notification_service.notify_available_drivers(payload)
            
            # [FIXED] Cleanup after successful processing
            await self._delete_from_queue(receipt_handle)

        except json.JSONDecodeError as je:
            logger.error(f"Malformed JSON in SQS message body: {je}")
            # [FIXED] Delete malformed message to clear the FIFO group
            await self._delete_from_queue(receipt_handle)
        except Exception as e:
            logger.error(f"Failed to process Trip SQS message: {e}", exc_info=True)

    async def _delete_from_queue(self, receipt_handle):
        """Helper to delete message from SQS FIFO queue"""
        try:
            await asyncio.to_thread(
                self.sqs.delete_message,
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
        except Exception as e:
            logger.error(f"Failed to delete message from SQS: {e}")

    def stop(self):
        """Signals the polling loop to stop during app shutdown"""
        self.running = False
