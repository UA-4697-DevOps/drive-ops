"""
Consumer for trip.event.created from Message Broker
UPDATED: Now tracks trip requests in storage for idempotency
"""
import json
import logging
from typing import Dict, Any
import pika

from services.driver_notification_service import DriverNotificationService
from schemas.trip_request import Location

logger = logging.getLogger(__name__)


class TripEventsConsumer:
    """Consumer for trip.event.created from Message Broker"""
    
    def __init__(
        self,
        rabbitmq_host: str,
        rabbitmq_port: int,
        rabbitmq_user: str,
        rabbitmq_pass: str,
        queue_name: str,
        notification_service: DriverNotificationService,
        trip_requests_storage: Dict[str, Dict[str, Any]] = None
    ):
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.rabbitmq_user = rabbitmq_user
        self.rabbitmq_pass = rabbitmq_pass
        self.queue_name = queue_name
        self.notification_service = notification_service
        self.trip_requests = trip_requests_storage if trip_requests_storage is not None else {}
        self.connection = None
        self.channel = None
        logger.info(f"TripEventsConsumer.__init__: received storage_id={id(trip_requests_storage)}, using storage_id={id(self.trip_requests)}")
    
    def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(self.rabbitmq_user, self.rabbitmq_pass)
            parameters = pika.ConnectionParameters(
                host=self.rabbitmq_host,
                port=self.rabbitmq_port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Declare exchange (ensure it exists)
            self.channel.exchange_declare(
                exchange='trip_events',
                exchange_type='topic',
                durable=True
            )

            # Declare queue
            self.channel.queue_declare(queue=self.queue_name, durable=True)

            # Bind queue to exchange with routing key
            self.channel.queue_bind(
                queue=self.queue_name,
                exchange='trip_events',
                routing_key='trip.event.created'
            )

            logger.info(f"Connected to RabbitMQ queue: {self.queue_name}")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    async def process_trip_created_event(self, event_data: Dict[str, Any]):
        """
        Process trip.event.created from Trip Service.
        [FIXED] Updated to handle camelCase keys from the Go service.
        """
        try:
            payload = event_data.get("payload", {})
            
            # [FIXED] Synchronized with new Go domain tags (camelCase)
            # We use .get() with fallbacks to maintain backward compatibility during the shift.
            trip_id = payload.get("tripId") or payload.get("trip_id")
            
            pickup_data = payload.get("pickup", {})
            
            logger.info(f"Processing trip.event.created for trip {trip_id}")
            
            # Check idempotency first
            if not trip_id:
                logger.error(f"Legacy Bridge: Missing tripId in payload. Keys: {list(payload.keys())}")
                return

            if trip_id in self.trip_requests:
                logger.info(f"Trip {trip_id} already tracked, skipping duplicate processing")
                return
            
            # Validate pickup coordinates
            pickup_lat = pickup_data.get("lat")
            pickup_lng = pickup_data.get("lng")
            
            if pickup_lat is None or pickup_lng is None:
                logger.error(f"Missing pickup coordinates for trip {trip_id}")
                return

            # Validate dropoff data
            dropoff_data = payload.get("dropoff", {})
            dropoff_lat = dropoff_data.get("lat")
            dropoff_lng = dropoff_data.get("lng")
            dropoff_address = dropoff_data.get("address")

            if dropoff_lat is None or dropoff_lng is None or not dropoff_address:
                logger.error(f"Missing or incomplete dropoff data for trip {trip_id}")
                return

            # Create notification data - Using UTC for consistency
            notification_data = {
                "pickup": Location(**pickup_data),
                "dropoff": Location(**dropoff_data),
                # [FIXED] Updated key to match new passengerId tag
                "passenger_name": payload.get("passengerId") or payload.get("passenger_id", "Unknown"),
                "estimated_distance_km": 5.0,
                "estimated_duration_min": 15,
                "fare_estimate": 100.0,
                "comment": None
            }
            
            notified_drivers = await self.notification_service.notify_nearby_drivers(
                trip_id=str(trip_id), # Ensure string conversion
                pickup_latitude=pickup_lat,
                pickup_longitude=pickup_lng,
                notification_data=notification_data,
                radius_km=5.0
            )
            
            # Track trip request in storage
            self.trip_requests[str(trip_id)] = {
                "status": "pending",
                "notified_drivers": notified_drivers,
                "responses": {},
                "created_at": event_data.get("timestamp", ""),
                "pickup": pickup_data,
                "dropoff": dropoff_data
            }
            
            logger.info(f"Tracked trip request {trip_id} (Legacy Bridge)")
            
        except Exception as e:
            logger.error(f"Error processing legacy trip created event: {e}", exc_info=True)
    
    def callback(self, ch, method, properties, body):
        """RabbitMQ callback for incoming messages"""
        try:
            event_data = json.loads(body)
            
            # [FIXED] Updated to handle both camelCase and snake_case for logging
            # Matches the update in process_trip_created_event
            event_type = event_data.get('eventType') or event_data.get('event_type')
            logger.info(f"Received legacy event: {event_type}")
            
            # [REFINED] Get the existing loop if possible, or create one.
            # Running asyncio from a synchronous pika callback
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            loop.run_until_complete(self.process_trip_created_event(event_data))
            
            # Manual Ack after successful async processing
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            logger.error(f"Error in RabbitMQ legacy callback: {e}", exc_info=True)
            # Nack and requeue so we don't lose the message on transient failure
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def start_consuming(self):
        """Start consuming messages with QOS=1 for reliability"""
        self.connect()
        # Ensure we only process one message at a time per consumer thread
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=self.callback
        )
        
        logger.info(f"Started consuming from legacy queue: {self.queue_name}")
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Thread-safe shutdown of the Pika BlockingConnection"""
        if self.connection and self.connection.is_open:
            logger.info("Stopping legacy consumer...")
            # Schedule the stop command on the Pika thread
            self.connection.add_callback_threadsafe(self.channel.stop_consuming)
