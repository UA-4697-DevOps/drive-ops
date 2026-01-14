from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    
    # Application
    APP_NAME: str = "Driver Service"
    DEBUG: bool = True
    PORT: int = 8082
    
    # RabbitMQ
    ENABLE_RABBITMQ: bool = False
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASS: str = "guest"
    TRIP_EVENTS_QUEUE: str = "trip.events"
    
    # Client Gateway (Telegram Bot)
    CLIENT_GATEWAY_URL: str = "http://localhost:8080"
    GATEWAY_TIMEOUT: int = 10
    
    # Driver Service Settings
    MAX_RETRY_ATTEMPTS: int = 3
    DRIVER_SEARCH_RADIUS_KM: float = 5.0
    MAX_DRIVERS_TO_NOTIFY: int = 10
    
    class SettingsConfig(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
        )
        
settings = Settings()
