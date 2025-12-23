#!/bin/bash
set -e

# Створюємо бази даних для мікросервісів
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE trip_db;
    CREATE DATABASE driver_db;
    GRANT ALL PRIVILEGES ON DATABASE trip_db TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON DATABASE driver_db TO $POSTGRES_USER;
EOSQL
