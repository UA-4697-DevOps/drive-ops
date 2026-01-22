from sqlalchemy import String, Boolean, BigInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from typing import Optional
import uuid
from datetime import datetime

# Це основний клас, який Alembic шукає в env.py
class Base(DeclarativeBase):
    pass

# Опис таблиці drivers
class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"Driver(id={self.id!r}, name={self.first_name!r})"

# Опис таблиці bot_users - зберігає стан користувачів Telegram бота
class BotUser(Base):
    __tablename__ = "bot_users"

    # Telegram chat_id як primary key (може бути дуже великим числом)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Поточна активна роль користувача ('driver' або 'passenger')
    current_role: Mapped[str] = mapped_column(String(20), nullable=False, default='passenger')

    # Зовнішній ключ до таблиці drivers (nullable, якщо користувач не зареєстрований як водій)
    driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('drivers.id', ondelete='SET NULL'),
        nullable=True
    )

    # Дані водія для відображення (копіюються з Driver при реєстрації)
    driver_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    car_description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Статус водія ('online', 'offline')
    driver_status: Mapped[str] = mapped_column(String(20), nullable=False, default='offline')

    # ID активної поїздки (якщо водій на поїздці)
    active_trip_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship до Driver (опціонально, для зручності)
    driver: Mapped[Optional["Driver"]] = relationship("Driver", foreign_keys=[driver_id])

    def __repr__(self) -> str:
        return f"BotUser(chat_id={self.telegram_chat_id!r}, role={self.current_role!r}, driver_id={self.driver_id!r})"
    