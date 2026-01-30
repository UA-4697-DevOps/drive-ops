from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

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
    # Added explicit DATABASE_URL to support the override in docker-compose
    DATABASE_URL: Optional[str] = None

    # --- AWS / SQS Settings (NEW) ---
    AWS_REGION: str = "us-east-2"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    SQS_ENDPOINT: Optional[str] = None
    SQS_DRIVER_ASSIGNED_URL: Optional[str] = None
    SQS_TRIP_COMPLETED_URL: Optional[str] = None

    # --- RabbitMQ Settings (Deprecated but kept for safety) ---
    ENABLE_RABBITMQ: bool = True
    RABBITMQ_HOST: str = "mq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    
    @property
    def RABBITMQ_PASS(self) -> str:
        return self.RABBITMQ_PASSWORD
    
    TRIP_EVENTS_QUEUE: str = "driver_service_trip_created"
    DRIVER_RESPONSES_QUEUE: str = "driver_service_responses"
    TRIP_EVENTS_EXCHANGE: str = "trip_events"
    
    # --- Client Gateway ---
    CLIENT_GATEWAY_URL: str = "http://client-gateway:8080" 
    GATEWAY_TIMEOUT: int = 10
    
    # --- Driver Business Logic Settings ---
    MAX_RETRY_ATTEMPTS: int = 3
    DRIVER_SEARCH_RADIUS_KM: float = 5.0
    MAX_DRIVERS_TO_NOTIFY: int = 10

settings = Settings()
