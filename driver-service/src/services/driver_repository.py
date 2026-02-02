from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.driver_models import Driver
from uuid import UUID

class DriverRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> Driver:
        """Створити нового водія"""
        driver = Driver(**kwargs)
        self.session.add(driver)
        await self.session.commit()
        await self.session.refresh(driver)
        return driver

    async def get_by_id(self, driver_id: UUID) -> Driver | None:
        """Отримати водія за ID"""
        result = await self.session.execute(select(Driver).where(Driver.id == driver_id))
        return result.scalar_one_or_none()

    async def get_by_phone_number(self, phone_number: str) -> Driver | None:
        """Отримати водія за номером телефону"""
        result = await self.session.execute(select(Driver).where(Driver.phone_number == phone_number))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Driver]:
        """Отримати список усіх водіїв"""
        result = await self.session.execute(select(Driver))
        return list(result.scalars().all())

    async def update(self, driver_id: UUID, **kwargs) -> Driver | None:
        """Оновити дані водія"""
        query = (
            update(Driver)
            .where(Driver.id == driver_id)
            .values(**kwargs)
            .returning(Driver)
        )
        result = await self.session.execute(query)
        await self.session.commit()
        return result.scalar_one_or_none()

    async def delete(self, driver_id: UUID) -> bool:
        """Видалити водія"""
        query = delete(Driver).where(Driver.id == driver_id)
        result = await self.session.execute(query)
        await self.session.commit()
        return result.rowcount > 0
