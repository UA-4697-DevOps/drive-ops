from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from models.driver import DriverModel
from uuid import UUID
from typing import List, Optional

class DriverRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, driver: DriverModel) -> DriverModel:
        self.session.add(driver)
        await self.session.commit()
        await self.session.refresh(driver)
        return driver

    async def get_by_id(self, driver_id: UUID) -> Optional[DriverModel]:
        result = await self.session.execute(
            select(DriverModel).filter(DriverModel.id == driver_id)
        )
        return result.scalars().first()

    async def get_by_telegram_id(self, tg_id: str) -> Optional[DriverModel]:
        """Для перевірки реєстрації в боті"""
        result = await self.session.execute(
            select(DriverModel).filter(DriverModel.telegram_id == tg_id)
        )
        return result.scalars().first()

    async def update_status(self, driver_id: UUID, status: str) -> Optional[DriverModel]:
        driver = await self.get_by_id(driver_id)
        if driver:
            driver.status = status.upper()
            await self.session.commit()
        return driver

    async def update_location(self, driver_id: UUID, lat: float, lon: float):
        """Оновлення координат водія для Phase 2"""
        driver = await self.get_by_id(driver_id)
        if driver:
            driver.last_lat = lat
            driver.last_lon = lon
            await self.session.commit()
        return driver

    async def count_online_drivers(self) -> int:
        """Для ендпоінту /health"""
        result = await self.session.execute(
            select(func.count(DriverModel.id)).filter(DriverModel.status == "ONLINE")
        )
        return result.scalar() or 0

    async def list_all(self, status: Optional[str] = None) -> List[DriverModel]:
        """Загальний список з фільтрацією"""
        query = select(DriverModel)
        if status:
            query = query.filter(DriverModel.status == status)
        result = await self.session.execute(query)
        return result.scalars().all()
