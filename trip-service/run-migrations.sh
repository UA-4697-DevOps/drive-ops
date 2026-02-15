#!/bin/sh
set -e

# Construct database URL from environment variables
# DB_SSL_MODE defaults to "disable" for local/Docker; set to "require" for RDS
DB_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:5432/${TRIP_DB_NAME}?sslmode=${DB_SSL_MODE:-disable}"

# Run migrations
exec migrate -path=/migrations/ -database "$DB_URL" up
