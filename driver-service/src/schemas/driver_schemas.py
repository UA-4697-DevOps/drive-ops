from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

class DriverBase(BaseModel):
    first_name: str = Field(..., max_length=50, description="Driver's first name")
    last_name: str = Field(..., max_length=50, description="Driver's last name")
    phone_number: str = Field(..., max_length=20, description="Driver's phone number")
    is_active: bool = True

class DriverCreate(DriverBase):
    """Схема для створення нового водія"""
    pass

class DriverResponse(DriverBase):
    """Схема для повернення даних про водія (з ID)"""
    id: UUID

    model_config = ConfigDict(from_attributes=True)