"""
Pydantic schemas for trip requests
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Location(BaseModel):
    """Location with coordinates and address"""
    address: str
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class TripRequestNotification(BaseModel):
    """Notification sent to driver about new trip request"""
    trip_id: str
    driver_id: str
    pickup: Location
    dropoff: Location
    passenger_name: str = "Unknown"
    estimated_distance_km: float = Field(default=0.0, ge=0)
    estimated_duration_min: int = Field(default=0, ge=0)
    fare_estimate: float = Field(default=0.0, ge=0)
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TripEventCreated(BaseModel):
    """Event schema from Trip Service - matches trip-events.md"""
    event_id: str
    event_type: str = "trip.event.created"
    event_version: str = "1.0"
    correlation_id: str
    timestamp: str
    payload: dict
