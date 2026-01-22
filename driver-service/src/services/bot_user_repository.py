"""Repository for BotUser database operations"""
import logging
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from src.driver_models import BotUser

logger = logging.getLogger(__name__)


class BotUserRepository:
    """Repository for managing bot users in the database"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_chat_id(self, chat_id: int) -> Optional[BotUser]:
        """Get bot user by telegram chat ID"""
        stmt = select(BotUser).where(BotUser.telegram_chat_id == chat_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> BotUser:
        """Create a new bot user"""
        bot_user = BotUser(**kwargs)
        self.db.add(bot_user)
        await self.db.commit()
        await self.db.refresh(bot_user)
        logger.info(f"Created bot user with chat_id={bot_user.telegram_chat_id}")
        return bot_user

    async def update(self, chat_id: int, **kwargs) -> Optional[BotUser]:
        """Update bot user fields"""
        stmt = (
            update(BotUser)
            .where(BotUser.telegram_chat_id == chat_id)
            .values(**kwargs)
            .returning(BotUser)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        updated = result.scalar_one_or_none()

        if updated:
            logger.info(f"Updated bot user chat_id={chat_id} with fields: {kwargs.keys()}")
        else:
            logger.warning(f"Bot user with chat_id={chat_id} not found for update")

        return updated

    async def get_or_create(self, chat_id: int, defaults: Optional[dict] = None) -> tuple[BotUser, bool]:
        """
        Get bot user by chat_id, or create if doesn't exist.
        Returns (bot_user, created) where created is True if new user was created.

        Race-safe: handles concurrent creation attempts by catching IntegrityError
        and retrieving the existing record.
        """
        bot_user = await self.get_by_chat_id(chat_id)
        if bot_user:
            return bot_user, False

        # Create new user with defaults
        create_data = {'telegram_chat_id': chat_id}
        if defaults:
            create_data.update(defaults)

        try:
            bot_user = await self.create(**create_data)
            return bot_user, True
        except IntegrityError:
            # Race condition: another process created the user between our check and create
            # Rollback the failed transaction and retrieve the existing user
            await self.db.rollback()
            logger.info(f"Concurrent creation detected for chat_id={chat_id}, retrieving existing user")

            bot_user = await self.get_by_chat_id(chat_id)
            if bot_user:
                return bot_user, False
            else:
                # This should never happen, but re-raise if it does
                logger.error(f"Failed to retrieve user after IntegrityError for chat_id={chat_id}")
                raise

    async def list_all(self) -> List[BotUser]:
        """Get all bot users"""
        stmt = select(BotUser)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, chat_id: int) -> bool:
        """Delete bot user by chat_id"""
        bot_user = await self.get_by_chat_id(chat_id)
        if not bot_user:
            return False

        await self.db.delete(bot_user)
        await self.db.commit()
        logger.info(f"Deleted bot user with chat_id={chat_id}")
        return True

    async def update_driver_registration(
        self,
        chat_id: int,
        driver_id: UUID,
        driver_name: str,
        car_description: str
    ) -> Optional[BotUser]:
        """Update bot user with driver registration info"""
        return await self.update(
            chat_id,
            driver_id=driver_id,
            driver_name=driver_name,
            car_description=car_description,
            current_role='driver'
        )

    async def update_role(self, chat_id: int, role: str) -> Optional[BotUser]:
        """Update user's current role"""
        return await self.update(chat_id, current_role=role)

    async def update_driver_status(self, chat_id: int, status: str) -> Optional[BotUser]:
        """Update driver's online/offline status"""
        return await self.update(chat_id, driver_status=status)

    async def set_active_trip(self, chat_id: int, trip_id: Optional[str]) -> Optional[BotUser]:
        """Set or clear active trip for driver"""
        return await self.update(chat_id, active_trip_id=trip_id)
