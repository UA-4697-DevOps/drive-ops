CREATE TYPE trip_status AS ENUM ('PENDING', 'ACTIVE', 'COMPLETED', 'CANCELLED');



CREATE TABLE IF NOT EXISTS trips (
    id UUID PRIMARY KEY,
    passenger_id UUID NOT NULL,
    driver_id UUID,
    pickup TEXT NOT NULL,
    dropoff TEXT NOT NULL,
    status trip_status NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX idx_trips_passenger_id ON trips(passenger_id);