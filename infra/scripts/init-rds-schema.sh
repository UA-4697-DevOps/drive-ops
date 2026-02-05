#!/bin/bash
set -euo pipefail

# ============================================================================
# Initialize RDS Database Schema
# ============================================================================
# This script connects to RDS and creates database schema using SQL commands
#
# Usage:
#   ./init-rds-schema.sh [environment]
#
# Examples:
#   ./init-rds-schema.sh dev
# ============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Validate and sanitize environment variable
ENV_RAW="${1:-dev}"

# Check if ENV contains only allowed characters (lowercase letters, digits, hyphens, underscores)
if [[ ! "$ENV_RAW" =~ ^[a-z0-9_-]+$ ]]; then
    echo -e "${RED}✗ ERROR: Invalid environment name: '$ENV_RAW'${NC}"
    echo -e "${YELLOW}Environment name must contain only lowercase letters, digits, hyphens, and underscores${NC}"
    echo ""
    echo "Valid examples: dev, staging, prod, dev-eu, test_1"
    exit 1
fi

# Use sanitized environment variable
ENV="$ENV_RAW"
RDS_INSTANCE="drive-ops-${ENV}-postgres"
SECRET_ID="drive-ops/${ENV}/rds/credentials"
AWS_REGION="${AWS_REGION:-us-east-2}"

echo -e "${BLUE}Initializing RDS Schema for ${ENV}...${NC}"
echo ""

# Get RDS endpoint
echo -e "${YELLOW}→ Fetching RDS info...${NC}"
DB_HOST=$(aws rds describe-db-instances \
    --db-instance-identifier "$RDS_INSTANCE" \
    --query 'DBInstances[0].Endpoint.Address' \
    --output text)

if [ -z "$DB_HOST" ] || [ "$DB_HOST" == "None" ]; then
    echo -e "${RED}✗ RDS instance not found${NC}"
    exit 1
fi

# Get credentials
SECRET_JSON=$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_ID" \
    --query SecretString \
    --output text)

# Validate SECRET_JSON is not empty
if [ -z "$SECRET_JSON" ] || [ "$SECRET_JSON" == "null" ]; then
    echo -e "${RED}ERROR: Failed to retrieve secret from Secrets Manager${NC}"
    echo -e "${YELLOW}Secret ID: $SECRET_ID${NC}"
    echo "Please ensure:"
    echo "  1. The secret exists in AWS Secrets Manager"
    echo "  2. You have proper IAM permissions to read it"
    echo "  3. AWS_REGION is set correctly (current: $AWS_REGION)"
    exit 1
fi

DB_USER=$(echo "$SECRET_JSON" | jq -r '.username')
DB_PASS=$(echo "$SECRET_JSON" | jq -r '.password')

# Validate DB_USER is not empty or null
if [ -z "$DB_USER" ] || [ "$DB_USER" == "null" ]; then
    echo -e "${RED}✗ ERROR: Username not found in secret${NC}"
    echo -e "${YELLOW}Secret ID: $SECRET_ID${NC}"
    echo "The secret must contain a 'username' field"
    exit 1
fi

# Validate DB_PASS is not empty or null
if [ -z "$DB_PASS" ] || [ "$DB_PASS" == "null" ]; then
    echo -e "${RED}✗ ERROR: Password not found in secret${NC}"
    echo -e "${YELLOW}Secret ID: $SECRET_ID${NC}"
    echo "The secret must contain a 'password' field"
    exit 1
fi

export PGPASSWORD="$DB_PASS"

echo -e "${GREEN}✓ Connected to: ${DB_HOST}${NC}"
echo ""

# ============================================================================
# Create Trip Service Database
# ============================================================================

echo -e "${BLUE}Creating Trip Service Database...${NC}"

TRIP_DB="drive_ops_${ENV}_trip"

psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -U "$DB_USER" -d postgres <<EOF
-- Create database if not exists
SELECT 'CREATE DATABASE ${TRIP_DB}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${TRIP_DB}')\gexec

\c ${TRIP_DB}

-- Trip Service Tables
CREATE TABLE IF NOT EXISTS trips (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    driver_id INTEGER,
    pickup_location VARCHAR(255) NOT NULL,
    dropoff_location VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trip_events (
    id SERIAL PRIMARY KEY,
    trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_trips_user_id ON trips(user_id);
CREATE INDEX IF NOT EXISTS idx_trips_driver_id ON trips(driver_id);
CREATE INDEX IF NOT EXISTS idx_trips_status ON trips(status);
CREATE INDEX IF NOT EXISTS idx_trip_events_trip_id ON trip_events(trip_id);

EOF

echo -e "${GREEN}✓ Trip database schema created${NC}"
echo ""

# ============================================================================
# Create Driver Service Database
# ============================================================================

echo -e "${BLUE}Creating Driver Service Database...${NC}"

DRIVER_DB="drive_ops_${ENV}_driver"

psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -U "$DB_USER" -d postgres <<EOF
-- Create database if not exists
SELECT 'CREATE DATABASE ${DRIVER_DB}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DRIVER_DB}')\gexec

\c ${DRIVER_DB}

-- Driver Service Tables
CREATE TABLE IF NOT EXISTS drivers (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    vehicle_info VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'offline',
    location POINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS driver_locations (
    id SERIAL PRIMARY KEY,
    driver_id INTEGER NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    location POINT NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_drivers_telegram_user_id ON drivers(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_drivers_status ON drivers(status);
CREATE INDEX IF NOT EXISTS idx_driver_locations_driver_id ON driver_locations(driver_id);

EOF

echo -e "${GREEN}✓ Driver database schema created${NC}"
echo ""

# ============================================================================
# Verify
# ============================================================================

echo -e "${BLUE}Verification:${NC}"

echo -e "${YELLOW}→ Trip database tables:${NC}"
psql -h "$DB_HOST" -U "$DB_USER" -d "$TRIP_DB" -c "\dt"

echo -e "${YELLOW}→ Driver database tables:${NC}"
psql -h "$DB_HOST" -U "$DB_USER" -d "$DRIVER_DB" -c "\dt"

echo ""
echo -e "${GREEN}✓ Schema initialization complete!${NC}"

unset PGPASSWORD
