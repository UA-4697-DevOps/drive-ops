from sqlalchemy import Column, String, Float, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
import uuid

Base = declarative_base()

class DriverModel(Base):
    __tablename__ = "drivers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    car_description = Column(Text)
    status = Column(String(20), default="OFFLINE")
    last_lat = Column(Float, nullable=True)
    last_lon = Column(Float, nullable=True)
    telegram_id = Column(String(50), unique=True)
    rating = Column(Float, default=5.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
  
