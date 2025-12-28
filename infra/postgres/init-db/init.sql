-- Таблиця для Trip Service
CREATE TABLE IF NOT EXISTS trips (
    id UUID PRIMARY KEY,
    passenger_id UUID NOT NULL,
    driver_id UUID,
    status VARCHAR(20) DEFAULT 'PENDING',
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблиця для Driver Service
CREATE TABLE IF NOT EXISTS drivers (
    id UUID PRIMARY KEY,
    name VARCHAR(100),
    is_available BOOLEAN DEFAULT TRUE,
    last_lat DOUBLE PRECISION,
    last_lon DOUBLE PRECISION
);
