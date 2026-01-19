from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # --- Application Settings ---
    APP_NAME: str = "Driver Service"
    DEBUG: bool = True
    PORT: int = 8082
    
    # --- Database Settings ---
    DB_HOST: str = "db"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DRIVER_DB_NAME: str = "driver_db"

    # --- RabbitMQ Settings ---
    ENABLE_RABBITMQ: bool = True
    RABBITMQ_HOST: str = "mq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    
    TRIP_EVENTS_QUEUE: str = "driver_service_trip_created"
    DRIVER_RESPONSES_QUEUE: str = "driver_service_responses"
    TRIP_EVENTS_EXCHANGE: str = "trip_events"
    
    # --- Client Gateway (Telegram Bot) ---
    # ВИПРАВЛЕНО: Змінено ім'я з GATEWAY_URL на CLIENT_GATEWAY_URL
    # Також переконайся, що хост правильний (зазвичай це назва сервісу в docker-compose, тобто client-gateway)
    CLIENT_GATEWAY_URL: str = "http://client-gateway:8080" 
    GATEWAY_TIMEOUT: int = 10
    
    # --- Driver Business Logic Settings ---
    MAX_RETRY_ATTEMPTS: int = 3
    DRIVER_SEARCH_RADIUS_KM: float = 5.0
    MAX_DRIVERS_TO_NOTIFY: int = 10

settings = Settings()
