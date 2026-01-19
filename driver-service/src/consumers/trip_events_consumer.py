import pika, json, logging, asyncio
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

class TripEventsConsumer:
    def __init__(self, settings, notification_service, session_factory: sessionmaker):
        # Исправлено: теперь корректно принимает объект settings
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
        credentials = pika.PlainCredentials(self.user, self.password)
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.host, port=self.port, credentials=credentials))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue_name, durable=True)
        logger.info(f"✅ Подключено к очереди: {self.queue_name}")

    def callback(self, ch, method, properties, body):
        try:
            data = json.loads(body)
            payload = data.get("payload", {})
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.notification_service.notify_nearby_drivers(
                trip_id=payload.get("trip_id"),
                pickup_latitude=payload["pickup"]["lat"],
                pickup_longitude=payload["pickup"]["lng"],
                notification_data=payload
            ))
            loop.close()
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"❌ Ошибка консьюмера: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def start_consuming(self):
        self.connect()
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=self.callback)
        self.channel.start_consuming()
