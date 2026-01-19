-- 1. Створюємо базу даних для Driver Service
-- Нагадування: trip_db створюється автоматично через змінну POSTGRES_DB у docker-compose
CREATE DATABASE driver_db;

-- 2. Підключаємось до бази водіїв для ініціалізації схеми
\c driver_db;

-- 3. Створюємо таблицю водіїв
-- Використовуємо UUID для відповідності архітектурі Drive-Ops
CREATE TABLE IF NOT EXISTS drivers (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    car_description TEXT NOT NULL,
    
    -- Статус водія: OFFLINE, ONLINE, AVAILABLE, ON_TRIP, NOTIFIED
    -- Використовуємо VARCHAR для гнучкості станів
    status VARCHAR(20) DEFAULT 'OFFLINE',
    
    -- Гео-дані для Phase 2 (Driver Discovery)
    last_lat DOUBLE PRECISION,
    last_lon DOUBLE PRECISION,
    
    -- Зв'язок з Telegram (Chat ID) для Client Gateway
    telegram_id VARCHAR(50) UNIQUE,
    
    -- Додаткові дані водія
    rating FLOAT DEFAULT 5.0,
    
    -- Часові мітки
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Створюємо індекси для оптимізації
-- Швидкий пошук водіїв, які готові прийняти замовлення
CREATE INDEX idx_drivers_status ON drivers(status) WHERE status = 'AVAILABLE' OR status = 'ONLINE';

-- Індекс для telegram_id, щоб Gateway швидко знаходив водія при вхідних командах
CREATE INDEX idx_drivers_telegram_id ON drivers(telegram_id);
