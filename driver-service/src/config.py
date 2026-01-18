from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Ігнорувати зайві змінні в .env
    )
    
    # --- Application Settings ---
    APP_NAME: str = "Driver Service"
    DEBUG: bool = True
    PORT: int = 8082
    
    # --- Database Settings (Task 3) ---
    # Дефолтні значення налаштовані для роботи в Docker (хост 'db')
    DB_HOST: str = "db"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DRIVER_DB_NAME: str = "driver_db"

    # --- RabbitMQ Settings (Tasks 1, 2, 4) ---
    # ENABLE_RABBITMQ ставимо True, бо це ядро логіки Phase 2/3
    ENABLE_RABBITMQ: bool = True
    RABBITMQ_HOST: str = "mq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASS: str = "guest"
    
    # Назви черг та обмінників
    TRIP_EVENTS_QUEUE: str = "driver_service_trip_created"
    DRIVER_RESPONSES_QUEUE: str = "driver_service_responses"
    TRIP_EVENTS_EXCHANGE: str = "trip_events"
    
    # --- Client Gateway (Telegram Bot) ---
    # Використовуємо ім'я сервісу з docker-compose
    CLIENT_GATEWAY_URL: str = "http://client-gateway-bot:8080"
    GATEWAY_TIMEOUT: int = 10
    
    # --- Driver Business Logic Settings ---
    MAX_RETRY_ATTEMPTS: int = 3
    DRIVER_SEARCH_RADIUS_KM: float = 5.0
    MAX_DRIVERS_TO_NOTIFY: int = 10


settings = Settings()
