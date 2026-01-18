import pika
import json
import logging
import asyncio
from schemas.driver_response import DriverResponseEvent
from services.driver_response_service import DriverResponseService

logger = logging.getLogger(__name__)

class DriverResponseConsumer:
    """Консюмер для обробки відповідей водія (Accept/Reject)"""

    def __init__(self, settings, response_service: DriverResponseService):
        # Отримуємо налаштування з об'єкта settings
        self.host = settings.RABBITMQ_HOST
        self.port = settings.RABBITMQ_PORT
        self.user = settings.RABBITMQ_USER
        self.password = settings.RABBITMQ_PASSWORD
        self.queue_name = settings.DRIVER_RESPONSES_QUEUE
        
        self.response_service = response_service
        self.connection = None
        self.channel = None

    def connect(self):
        credentials = pika.PlainCredentials(self.user, self.password)
        parameters = pika.ConnectionParameters(host=self.host, port=self.port, credentials=credentials)
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue_name, durable=True)
        logger.info(f"✅ DriverResponseConsumer підключено до черги: {self.queue_name}")

    def callback(self, ch, method, properties, body):
        try:
            data = json.loads(body)
            event = DriverResponseEvent(payload=data)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(
                self.response_service.process_driver_response(event)
            )
            loop.close()

            if success:
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                
        except Exception as e:
            logger.error(f"❌ Помилка у DriverResponseConsumer: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def start_consuming(self):
        self.connect()
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=self.callback)
        logger.info(f"[*] DriverResponseConsumer очікує повідомлень у {self.queue_name}...")
        self.channel.start_consuming()

    def stop(self):
        if self.connection and self.connection.is_open:
            self.connection.add_callback_threadsafe(self.channel.stop_consuming)
