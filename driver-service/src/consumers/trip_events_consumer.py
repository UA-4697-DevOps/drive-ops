"""
Consumer for trip.event.created from Message Broker
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
        queue_name: str,
        notification_service: DriverNotificationService
    ):
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.queue_name = queue_name
        self.notification_service = notification_service
        self.connection = None
        self.channel = None
    
    def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            credentials = pika.PlainCredentials('guest', 'guest')
            parameters = pika.ConnectionParameters(
                host=self.rabbitmq_host,
                port=self.rabbitmq_port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=self.queue_name, durable=True)
            logger.info(f"Connected to RabbitMQ queue: {self.queue_name}")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    async def process_trip_created_event(self, event_data: Dict[str, Any]):
        """
        Process trip.event.created from Trip Service
        
        Event structure (from trip-events.md):
        {
            "event_type": "trip.event.created",
            "payload": {
                "trip_id": "...",
                "passenger_id": "...",
                "pickup": {"address": "...", "lat": 50.45, "lng": 30.52},
                "dropoff": {"address": "...", "lat": 50.46, "lng": 30.53}
            }
        }
        """
        try:
            payload = event_data.get("payload", {})
            trip_id = payload.get("trip_id")
            pickup_data = payload.get("pickup", {})
            
            logger.info(f"Processing trip.event.created for trip {trip_id}")
            
            pickup_lat = pickup_data.get("lat")
            pickup_lng = pickup_data.get("lng")
            
            if not pickup_lat or not pickup_lng:
                logger.error(f"Missing pickup coordinates for trip {trip_id}")
                return
            
            notification_data = {
                "pickup": Location(**pickup_data),
                "dropoff": Location(**payload.get("dropoff", {})),
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
        """Stop consuming and close connection"""
        if self.channel:
            self.channel.stop_consuming()
        if self.connection and not self.connection.is_closed:
            self.connection.close()
        logger.info("Stopped consuming")
