-- 1. Створюємо базу даних для Driver Service
-- Нагадування: trip_db створюється автоматично через змінну POSTGRES_DB у docker-compose
CREATE DATABASE driver_db;

-- Примітка: Схема таблиці drivers створюється через Alembic міграції
-- (driver-service/alembic/versions/42f496ca8ae8_init_drivers_table.py)
