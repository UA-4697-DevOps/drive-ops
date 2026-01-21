#!/bin/sh
set -e

# Construct database URL from environment variables
DB_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:5432/${TRIP_DB_NAME}?sslmode=disable"

# Run migrations
exec migrate -path=/migrations/ -database "$DB_URL" up
