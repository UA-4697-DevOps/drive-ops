from sqlalchemy import Column, String, Float, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base
from pydantic import BaseModel
import uuid

Base = declarative_base()

# --- Database Model (SQLAlchemy) ---
class DriverModel(Base):
    __tablename__ = "drivers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    car_description = Column(Text, nullable=False)
    status = Column(String(20), default="OFFLINE")
    
    # Координати для розрахунків у geo.py
    last_lat = Column(Float, nullable=True)
    last_lon = Column(Float, nullable=True)
    
    telegram_id = Column(String(50), unique=True)
    rating = Column(Float, default=5.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# --- Pydantic Schemas (FastAPI DTOs) ---
class DriverCreate(BaseModel):
    """Схема для створення водія"""
    name: str
    car_description: str
    telegram_id: str

class DriverUpdateLocation(BaseModel):
    """Схема для оновлення локації"""
    location: str  # Формат "50.45,30.52"
