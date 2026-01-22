"""Pydantic schemas for BotUser model"""
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class BotUserBase(BaseModel):
    """Base schema with common fields"""
    telegram_chat_id: int = Field(..., description="Telegram chat ID of the user")
    current_role: str = Field(default='passenger', description="Current active role: 'driver' or 'passenger'")


class BotUserCreate(BotUserBase):
    """Schema for creating a new bot user"""
    pass


class BotUserUpdate(BaseModel):
    """Schema for updating bot user (all fields optional)"""
    current_role: Optional[str] = None
    driver_id: Optional[UUID] = None
    driver_name: Optional[str] = None
    car_description: Optional[str] = None
    driver_status: Optional[str] = None
    active_trip_id: Optional[str] = None


class BotUserResponse(BotUserBase):
    """Schema for returning bot user data"""
    driver_id: Optional[UUID] = None
    driver_name: Optional[str] = None
    car_description: Optional[str] = None
    driver_status: str
    active_trip_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BotUserDriverRegistration(BaseModel):
    """Schema for registering user as driver"""
    telegram_chat_id: int
    driver_name: str = Field(..., min_length=2, max_length=100)
    car_description: str = Field(..., min_length=5, max_length=200)
