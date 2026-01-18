from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
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
        result = await self.session.execute(select(DriverModel).filter(DriverModel.id == driver_id))
        return result.scalars().first()

    async def update_status(self, driver_id: UUID, status: str):
        driver = await self.get_by_id(driver_id)
        if driver:
            driver.status = status.upper()
            await self.session.commit()
        return driver

    async def get_online_drivers(self) -> List[DriverModel]:
        """Task 1 & 5: Пошук водіїв для замовлень"""
        result = await self.session.execute(
            select(DriverModel).filter(DriverModel.status.in_(["ONLINE", "AVAILABLE"]))
        )
        return result.scalars().all()
