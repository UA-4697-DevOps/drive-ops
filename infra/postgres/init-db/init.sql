-- 1. Create the second database for Driver Service
-- Note: trip_db is created automatically by Docker via POSTGRES_DB environment variable
CREATE DATABASE driver_db;

-- 2. Connect to trip_db to initialize its schema
\c trip_db;

-- Table for Trip Service
CREATE TABLE IF NOT EXISTS trips (
    id UUID PRIMARY KEY,
    passenger_id UUID NOT NULL,
    driver_id UUID,
    status VARCHAR(20) DEFAULT 'PENDING',
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Connect to driver_db to initialize its schema
\c driver_db;

-- Table for Driver Service
CREATE TABLE IF NOT EXISTS drivers (
    id UUID PRIMARY KEY,
    name VARCHAR(100),
    is_available BOOLEAN DEFAULT TRUE,
    last_lat DOUBLE PRECISION,
    last_lon DOUBLE PRECISION
);
