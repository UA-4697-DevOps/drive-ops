from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

class DriverBase(BaseModel):
    first_name: str = Field(..., max_length=50, description="Driver's first name")
    last_name: str = Field(..., max_length=50, description="Driver's last name")
    phone_number: str = Field(..., max_length=20, description="Driver's phone number")
    is_active: bool = True

class DriverCreate(DriverBase):
    """Schema for creating a new driver"""
    pass

class DriverResponse(DriverBase):
    """Schema for returning driver data (including ID)"""
    id: UUID

    model_config = ConfigDict(from_attributes=True)

class LocationUpdate(BaseModel):
    """Schema for updating driver GPS coordinates with validation"""
    lat: float = Field(..., ge=-90, le=90, description="Latitude (-90 to 90)")
    lng: float = Field(..., ge=-180, le=180, description="Longitude (-180 to 180)")

