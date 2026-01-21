"""
Event schemas for driver responses to trip requests
"""
from pydantic import BaseModel, Field, field_serializer
from datetime import datetime, timezone
from typing import Literal


class DriverResponsePayload(BaseModel):
    """Payload for driver.cmd.trip_accept and driver.cmd.trip_reject"""
    driver_id: str = Field(..., description="ID of the driver responding")
    trip_id: str = Field(..., description="ID of the trip being responded to")
    decision: Literal["accept", "reject"] = Field(..., description="Driver's decision")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Response timestamp")


class DriverResponseEvent(BaseModel):
    """
    Event structure for driver responses

    Commands from Client Gateway (Telegram Bot):
    - driver.cmd.trip_accept
    - driver.cmd.trip_reject
    """
    event_type: Literal["driver.cmd.trip_accept", "driver.cmd.trip_reject"]
    payload: DriverResponsePayload


class DriverAssignedPayload(BaseModel):
    """Payload for trip.event.driver_assigned"""
    trip_id: str = Field(..., description="ID of the trip")
    driver_id: str = Field(..., description="ID of assigned driver")
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Assignment timestamp")

    @field_serializer('assigned_at')
    def serialize_assigned_at(self, value: datetime) -> str:
        """Serialize datetime to RFC3339 format with Z suffix for Go compatibility"""
        # Normalize to UTC
        if value.tzinfo is not None:
            # Convert timezone-aware datetime to UTC
            value = value.astimezone(timezone.utc)
        else:
            # Treat timezone-naive datetime as UTC
            value = value.replace(tzinfo=timezone.utc)

        # Get ISO format and replace +00:00 with Z for RFC3339
        iso = value.isoformat()
        return iso.replace('+00:00', 'Z')


class DriverAssignedEvent(BaseModel):
    """
    Event to publish when driver accepts trip
    
    Published to Trip Service:
    - trip.event.driver_assigned
    """
    event_type: str = Field(default="trip.event.driver_assigned")
    payload: DriverAssignedPayload
