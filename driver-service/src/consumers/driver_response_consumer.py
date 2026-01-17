"""
Consumer for driver response events (driver.cmd.trip_accept, driver.cmd.trip_reject)
"""
import json
import logging
from typing import Dict, Any
import pika

from services.driver_response_service import DriverResponseService
from schemas.driver_response import DriverResponseEvent

logger = logging.getLogger(__name__)


class DriverResponseConsumer:
    """Consumer for driver accept/reject responses from Client Gateway"""
    
    def __init__(
        self,
        rabbitmq_host: str,
        rabbitmq_port: int,
        rabbitmq_user: str,
        rabbitmq_pass: str,
        queue_name: str,
        response_service: DriverResponseService
    ):
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.rabbitmq_user = rabbitmq_user
        self.rabbitmq_pass = rabbitmq_pass
        self.queue_name = queue_name
        self.response_service = response_service
        self.connection = None
        self.channel = None
    
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
            self.channel.queue_declare(queue=self.queue_name, durable=True)
            logger.info(f"Connected to RabbitMQ queue: {self.queue_name}")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    async def process_driver_response_event(self, event_data: Dict[str, Any]) -> bool:
        """
        Process driver response events
        
        Event types:
        - driver.cmd.trip_accept
        - driver.cmd.trip_reject
        
        Returns:
            True if processed successfully, False otherwise
        """
        try:
            event_type = event_data.get("event_type")
            
            # FIXED: Unknown event types are non-retriable - drop them (return True)
            if event_type not in ["driver.cmd.trip_accept", "driver.cmd.trip_reject"]:
                logger.warning(f"Unknown event type: {event_type} (dropping message)")
                return True  # ACK to prevent poison message retry loop
            
            # Validate and parse event
            event = DriverResponseEvent(**event_data)
            
            logger.info(
                f"Processing {event_type} - "
                f"Driver: {event.payload.driver_id}, "
                f"Trip: {event.payload.trip_id}"
            )
            
            # Process response
            success = await self.response_service.process_driver_response(event)
            
            if success:
                logger.info(
                    f"Successfully processed {event_type} - "
                    f"Driver: {event.payload.driver_id}, "
                    f"Trip: {event.payload.trip_id}"
                )
            else:
                logger.error(
                    f"Failed to process {event_type} - "
                    f"Driver: {event.payload.driver_id}, "
                    f"Trip: {event.payload.trip_id}"
                )
            
            return success
            
        except Exception as e:
            logger.error(
                f"Error processing driver response event: {e}",
                exc_info=True
            )
            return False
    
    def callback(self, ch, method, properties, body):
        """RabbitMQ callback for incoming messages"""
        try:
            event_data = json.loads(body)
            event_type = event_data.get("event_type")
            logger.info(f"Received event: {event_type}")
            
            import asyncio
            success = asyncio.run(self.process_driver_response_event(event_data))
            
            if success:
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                # Requeue on failure for retry
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            
        except Exception as e:
            logger.error(f"Error in callback: {e}", exc_info=True)
            # Requeue on error for retry
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
