from pydantic import model_validator
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
    DATABASE_URL: Optional[str] = None

    # --- AWS / SQS Settings ---
    AWS_REGION: str = "us-east-2"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None

    # Queue URLs for Trip Lifecycle (Primary Event Bus)
    SQS_TRIP_CREATED_URL: Optional[str] = None
    SQS_DRIVER_ASSIGNED_URL: Optional[str] = None
    SQS_TRIP_COMPLETED_URL: Optional[str] = None

    # --- Client Gateway ---
    CLIENT_GATEWAY_URL: Optional[str] = None
    GATEWAY_TIMEOUT: int = 10

    @model_validator(mode="after")
    def require_runtime_vars(self) -> "Settings":
        missing = [
            name for name, val in {
                "SQS_TRIP_CREATED_URL": self.SQS_TRIP_CREATED_URL,
                "SQS_DRIVER_ASSIGNED_URL": self.SQS_DRIVER_ASSIGNED_URL,
                "SQS_TRIP_COMPLETED_URL": self.SQS_TRIP_COMPLETED_URL,
                "CLIENT_GATEWAY_URL": self.CLIENT_GATEWAY_URL,
            }.items()
            if not val
        ]
        if missing:
            raise ValueError(f"❌ Required env vars not set: {', '.join(missing)}")
        return self
    
    # --- Driver Business Logic Settings ---
    MAX_RETRY_ATTEMPTS: int = 3
    DRIVER_SEARCH_RADIUS_KM: float = 5.0
    MAX_DRIVERS_TO_NOTIFY: int = 10

settings = Settings()
