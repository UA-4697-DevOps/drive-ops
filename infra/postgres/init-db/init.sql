-- 1. Створюємо базу даних для Driver Service
-- Нагадування: trip_db створюється автоматично через змінну POSTGRES_DB у docker-compose
CREATE DATABASE driver_db;

-- 2. Підключаємось до бази водіїв для ініціалізації схеми
\c driver_db;

-- 3. Створюємо таблицю водіїв
-- Схема синхронізована з ORM моделлю (driver-service/src/driver_models.py)
CREATE TABLE IF NOT EXISTS drivers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    phone_number VARCHAR(20) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE
);

-- 4. Створюємо індекси для оптимізації
-- Швидкий пошук активних водіїв
CREATE INDEX IF NOT EXISTS idx_drivers_is_active ON drivers(is_active) WHERE is_active = TRUE;

-- Індекс для пошуку за номером телефону (підтримка unique constraint)
CREATE INDEX IF NOT EXISTS idx_drivers_phone_number ON drivers(phone_number);
