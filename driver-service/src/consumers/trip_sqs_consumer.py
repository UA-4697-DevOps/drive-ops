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
        # [FIXED] Removed SQS_ENDPOINT override to use standard AWS SQS URLs
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
                # Long polling (10s) to balance latency and AWS costs
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
                    await self.process_message(msg)

            except Exception as e:
                logger.error(f"Critical error in Trip SQS polling loop: {e}")
                await asyncio.sleep(5) # Cooldown before retrying

    async def process_message(self, message):
        """
        Processes a single SQS message from the trip-created queue.
        Maps Go's snake_case JSON to the Python in-memory storage.
        """
        try:
            body = json.loads(message['Body'])
            
            # The Go service sends the data wrapped in a 'payload' object
            payload = body.get('payload', {})
            
            # Go serializes UUIDs as 'trip_id' (snake_case)
            trip_id = payload.get('trip_id')
            
            if not trip_id:
                logger.error(f"Missing trip_id in SQS payload. Keys: {list(payload.keys())}")
                return

            # Use string representation for consistent dictionary lookups
            trip_id_str = str(trip_id)
            logger.info(f"Processing new trip via SQS: {trip_id_str}")

            # 1. Sync In-Memory State for driver discovery
            self.trip_requests[trip_id_str] = {
                "status": "pending",
                "pickup": payload.get('pickup'),
                "dropoff": payload.get('dropoff'),
                "created_at": body.get('timestamp'), # Use envelope timestamp
                "notified_drivers": [],
                "responses": {}
            }

            # 2. Trigger driver notifications
            await self.notification_service.notify_available_drivers(payload)

            # 3. Cleanup: Delete processed message from FIFO queue
            await asyncio.to_thread(
                self.sqs.delete_message,
                QueueUrl=self.queue_url,
                ReceiptHandle=message['ReceiptHandle']
            )
            
        except json.JSONDecodeError as je:
            logger.error(f"Malformed JSON in SQS message body: {je}")
        except Exception as e:
            logger.error(f"Failed to process Trip SQS message: {e}", exc_info=True)

    def stop(self):
        self.running = False
