import pika
import json
import logging
import asyncio
from sqlalchemy.orm import sessionmaker
from services.driver_notification_service import DriverNotificationService

logger = logging.getLogger(__name__)

class TripEventsConsumer:
    """Консюмер для отримання подій про нові поїздки від Trip Service"""
    
    def __init__(
        self,
        settings,
        notification_service: DriverNotificationService,
        session_factory: sessionmaker
    ):
        # Отримуємо налаштування з об'єкта settings
        self.host = settings.RABBITMQ_HOST
        self.port = settings.RABBITMQ_PORT
        self.user = settings.RABBITMQ_USER
        self.password = settings.RABBITMQ_PASSWORD
        self.queue_name = settings.TRIP_EVENTS_QUEUE
        
        self.notification_service = notification_service
        self.session_factory = session_factory
        self.connection = None
        self.channel = None

    def connect(self):
        """Встановлення з'єднання з RabbitMQ"""
        credentials = pika.PlainCredentials(self.user, self.password)
        parameters = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=credentials,
            heartbeat=600
        )
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue_name, durable=True)
        logger.info(f"✅ TripEventsConsumer підключено до черги: {self.queue_name}")

    def callback(self, ch, method, properties, body):
        try:
            event_data = json.loads(body)
            payload = event_data.get("payload", {})
            trip_id = payload.get("trip_id")

            logger.info(f" [x] Отримано замовлення: {trip_id}")

            # Запускаємо асинхронну логіку в синхронному консюмері
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self.notification_service.notify_nearby_drivers(
                    trip_id=trip_id,
                    pickup_latitude=payload["pickup"]["lat"],
                    pickup_longitude=payload["pickup"]["lng"],
                    notification_data=payload
                )
            )
            loop.close()

            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"❌ Помилка в TripEventsConsumer: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def start_consuming(self):
        self.connect()
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=self.callback)
        logger.info(f"[*] TripEventsConsumer очікує повідомлень у {self.queue_name}...")
        self.channel.start_consuming()

    def stop(self):
        if self.connection and self.connection.is_open:
            self.connection.add_callback_threadsafe(self.channel.stop_consuming)
