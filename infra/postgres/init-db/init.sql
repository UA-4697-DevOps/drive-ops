-- 1. Create the second database for Driver Service (Python)
-- Note: trip_db is created automatically by Docker via POSTGRES_DB environment variable
CREATE DATABASE driver_db;

-- 2. Connect to driver_db to initialize its schema
\c driver_db;

-- 3. Table for Driver Service (Python)
-- We use UUID for consistency across all microservices in drive-ops
CREATE TABLE IF NOT EXISTS drivers (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    last_lat DOUBLE PRECISION,
    last_lon DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
