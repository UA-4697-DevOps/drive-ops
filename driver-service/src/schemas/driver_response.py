"""
Event schemas for driver responses to trip requests
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal


class DriverResponsePayload(BaseModel):
    """Payload for driver.cmd.trip_accept and driver.cmd.trip_reject"""
    driver_id: str = Field(..., description="ID of the driver responding")
    trip_id: str = Field(..., description="ID of the trip being responded to")
    decision: Literal["accept", "reject"] = Field(..., description="Driver's decision")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    

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
    assigned_at: datetime = Field(default_factory=datetime.utcnow, description="Assignment timestamp")


class DriverAssignedEvent(BaseModel):
    """
    Event to publish when driver accepts trip
    
    Published to Trip Service:
    - trip.event.driver_assigned
    """
    event_type: str = Field(default="trip.event.driver_assigned")
    payload: DriverAssignedPayload
