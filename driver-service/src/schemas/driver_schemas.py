from pydantic import BaseModel, ConfigDict
from uuid import UUID

class DriverBase(BaseModel):
    first_name: str
    last_name: str
    phone_number: str
    is_active: bool = True

class DriverCreate(DriverBase):
    """Схема для створення нового водія"""
    pass

class DriverResponse(DriverBase):
    """Схема для повернення даних про водія (з ID)"""
    id: UUID

    model_config = ConfigDict(from_attributes=True)