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
        """Process trip.event.created from Trip Service"""
        try:
            payload = event_data.get("payload", {})
            trip_id = payload.get("trip_id")
            pickup_data = payload.get("pickup", {})
            
            logger.info(f"Processing trip.event.created for trip {trip_id}")
            
            # Check idempotency first
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

            # Create notification data
            notification_data = {
                "pickup": Location(**pickup_data),
                "dropoff": Location(**dropoff_data),
                "passenger_name": payload.get("passenger_id", "Unknown"),
                "estimated_distance_km": 5.0,
                "estimated_duration_min": 15,
                "fare_estimate": 100.0,
                "comment": None
            }
            
            notified_drivers = await self.notification_service.notify_nearby_drivers(
                trip_id=trip_id,
                pickup_latitude=pickup_lat,
                pickup_longitude=pickup_lng,
                notification_data=notification_data,
                radius_km=5.0
            )
            
            # Track trip request in storage
            self.trip_requests[trip_id] = {
                "status": "pending",
                "notified_drivers": notified_drivers,
                "responses": {},
                "created_at": event_data.get("timestamp", ""),
                "pickup": pickup_data,
                "dropoff": dropoff_data
            }
            logger.info(f"Tracked trip request {trip_id} in storage (storage_id={id(self.trip_requests)}, total_trips={len(self.trip_requests)})")
            
            logger.info(
                f"Trip {trip_id} processing complete. "
                f"Notified {len(notified_drivers)} drivers: {notified_drivers}"
            )
            
        except Exception as e:
            logger.error(
                f"Error processing trip.event.created: {e}",
                exc_info=True
            )
    
    def callback(self, ch, method, properties, body):
        """RabbitMQ callback for incoming messages"""
        try:
            event_data = json.loads(body)
            logger.info(f"Received event: {event_data.get('event_type')}")
            
            import asyncio
            asyncio.run(self.process_trip_created_event(event_data))
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            logger.error(f"Error in callback: {e}", exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def start_consuming(self):
        """Start consuming messages"""
        self.connect()
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=self.callback
        )
        
        logger.info(f"Started consuming from {self.queue_name}")
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Stopping consumer...")
            self.stop()
    
    def stop(self):
        """Stop consuming and close connection (thread-safe)"""
        # FIXED: Use thread-safe callback for pika BlockingConnection
        if self.connection and self.connection.is_open and self.channel:
            try:
                self.connection.add_callback_threadsafe(self.channel.stop_consuming)
            except Exception as e:
                logger.error(f"Error stopping consumer: {e}")
        # Connection will close automatically after stop_consuming completes
        logger.info("Consumer stop requested")
