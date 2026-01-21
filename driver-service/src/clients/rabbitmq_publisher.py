"""
RabbitMQ publisher for sending events to other services
"""
import json
import logging
import pika
from typing import Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    """Publisher for sending events to RabbitMQ exchanges"""
    
    def __init__(
        self,
        rabbitmq_host: str,
        rabbitmq_port: int,
        rabbitmq_user: str,
        rabbitmq_pass: str,
        exchange_name: str = "trip.events"
    ):
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.rabbitmq_user = rabbitmq_user
        self.rabbitmq_pass = rabbitmq_pass
        self.exchange_name = exchange_name
        self.connection = None
        self.channel = None
    
    def _fix_datetime_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively fix datetime strings to have 'Z' suffix for Go RFC3339 parsing

        Args:
            data: Dictionary that may contain datetime strings

        Returns:
            Dictionary with fixed datetime strings
        """
        if not isinstance(data, dict):
            return data

        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                # Check if it looks like ISO datetime without 'Z'
                # Format: YYYY-MM-DDTHH:MM:SS.microseconds
                if 'T' in value and not value.endswith('Z') and not value.endswith('+00:00'):
                    # Add 'Z' suffix for UTC timezone
                    result[key] = value + 'Z'
                else:
                    result[key] = value
            elif isinstance(value, dict):
                result[key] = self._fix_datetime_format(value)
            else:
                result[key] = value

        return result

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
            
            # Declare exchange (idempotent)
            self.channel.exchange_declare(
                exchange=self.exchange_name,
                exchange_type='topic',
                durable=True
            )
            
            logger.info(f"Connected to RabbitMQ exchange: {self.exchange_name}")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    def publish_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        routing_key: str = None
    ) -> bool:
        """
        Publish event to RabbitMQ exchange

        Args:
            event_type: Type of event (e.g., 'trip.event.driver_assigned')
            payload: Event payload
            routing_key: Optional routing key (defaults to event_type)

        Returns:
            True if published successfully, False otherwise
        """
        if not routing_key:
            routing_key = event_type

        try:
            # Ensure connection and channel (FIXED: added channel check)
            if not self.connection or self.connection.is_closed or not self.channel or self.channel.is_closed:
                self.connect()

            # Fix all datetime strings in payload to have 'Z' suffix for Go RFC3339 parsing
            fixed_payload = self._fix_datetime_format(payload)

            event_data = {
                "event_type": event_type,
                "payload": fixed_payload,
                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }

            message = json.dumps(event_data)
            
            self.channel.basic_publish(
                exchange=self.exchange_name,
                routing_key=routing_key,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json'
                )
            )
            
            logger.info(
                f"Published event: {event_type} with routing key: {routing_key}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish event {event_type}: {e}")
            return False
    
    def close(self):
        """Close connection to RabbitMQ"""
        try:
            if self.channel and self.channel.is_open:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Closed RabbitMQ connection")
        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {e}")
