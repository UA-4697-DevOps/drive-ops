#!/bin/bash
set -euo pipefail

# ============================================================================
# Run database migrations for all services via SSM Run Command
# ============================================================================
# - trip-service:    applies SQL migrations via psql on the EC2 instance
# - driver-service:  runs "alembic upgrade head" inside the running container
#
# Prerequisites:
#   - 03-deploy-services.sh must have run successfully (containers must be up)
#   - EC2 instances must have SSM agent active
#   - psql must be installed on the trip-service instance
#
# Usage:
#   ./04-run-migrations.sh [dev|staging|prod]
# ============================================================================

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- Config ---
ENV_RAW="${1:-dev}"
if [[ ! "$ENV_RAW" =~ ^[a-z0-9_-]+$ ]]; then
  echo -e "${RED}✗ Invalid environment: '$ENV_RAW'${NC}"; exit 1
fi

ENV="$ENV_RAW"
PROJECT="drive-ops"
REGION="${AWS_REGION:-us-east-2}"
POLL_INTERVAL=5
TIMEOUT=120

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  Run migrations — env=${ENV}${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# ============================================================
# Helper: get running instance ID by service tag
# ============================================================
get_instance_id() {
  aws ec2 describe-instances \
    --region "$REGION" \
    --filters \
      "Name=tag:Service,Values=$1" \
      "Name=instance-state-name,Values=running" \
    --query 'Reservations[0].Instances[0].InstanceId' \
    --output text
}

# ============================================================
# Helper: run SSM command and wait for result
# ============================================================
run_ssm() {
  local label="$1"
  local instance_id="$2"
  shift 2
  # remaining args are command lines array
  local commands_json
  commands_json=$(printf '%s\n' "$@" | jq -R . | jq -s .)

  echo -e "${YELLOW}→ ${label} (${instance_id})...${NC}"

  COMMAND_ID=$(aws ssm send-command \
    --region "$REGION" \
    --instance-ids "$instance_id" \
    --document-name "AWS-RunShellScript" \
    --parameters "commands=${commands_json}" \
    --comment "$label" \
    --query 'Command.CommandId' \
    --output text)

  echo -e "  Command ID: ${CYAN}${COMMAND_ID}${NC}"

  elapsed=0
  while true; do
    STATUS=$(aws ssm get-command-invocation \
      --region "$REGION" \
      --command-id "$COMMAND_ID" \
      --instance-id "$instance_id" \
      --query 'StatusDetails' \
      --output text 2>/dev/null || echo "Pending")

    case "$STATUS" in
      Success)
        echo -e "  ${GREEN}✓ ${label} completed${NC}"
        # Print stdout for visibility
        aws ssm get-command-invocation \
          --region "$REGION" \
          --command-id "$COMMAND_ID" \
          --instance-id "$instance_id" \
          --query 'StandardOutputContent' \
          --output text 2>/dev/null | grep -v '^$' | sed 's/^/    /'
        return 0
        ;;
      Failed|Cancelled|TimedOut|Undeliverable|Terminated)
        echo -e "  ${RED}✗ ${label} FAILED (status: $STATUS)${NC}"
        aws ssm get-command-invocation \
          --region "$REGION" \
          --command-id "$COMMAND_ID" \
          --instance-id "$instance_id" \
          --query 'StandardErrorContent' \
          --output text 2>/dev/null | tail -20 | sed 's/^/    /'
        return 1
        ;;
      *)
        if (( elapsed >= TIMEOUT )); then
          echo -e "  ${RED}✗ Timed out after ${TIMEOUT}s${NC}"
          return 1
        fi
        printf "  Waiting... (%ds) status=%s\r" "$elapsed" "$STATUS"
        sleep "$POLL_INTERVAL"
        (( elapsed += POLL_INTERVAL ))
        ;;
    esac
  done
}

# ============================================================
# 1. trip-service migrations (SQL via psql)
# ============================================================
echo -e "${BLUE}→ trip-service migrations${NC}"

TRIP_INSTANCE=$(get_instance_id "trip-service")
if [[ -z "$TRIP_INSTANCE" || "$TRIP_INSTANCE" == "None" ]]; then
  echo -e "${RED}✗ No running trip-service instance found${NC}"; exit 1
fi

TRIP_NAME="Training-${PROJECT}-${ENV}-trip-service"

run_ssm "trip-service: apply SQL migrations" "$TRIP_INSTANCE" \
  "set -e" \
  "export AWS_DEFAULT_REGION=${REGION}" \
  "ENV_FILE=/opt/${TRIP_NAME}/.env" \
  "if [ ! -f \"\$ENV_FILE\" ]; then echo 'ERROR: .env not found at \$ENV_FILE'; exit 1; fi" \
  "DB_URL=\$(grep '^DB_URL=' \"\$ENV_FILE\" | cut -d= -f2-)" \
  "if [ -z \"\$DB_URL\" ]; then echo 'ERROR: DB_URL not found in .env'; exit 1; fi" \
  "echo 'Running trip-service SQL migrations...'" \
  "psql \"\$DB_URL\" <<'ENDSQL'" \
  "DO \$\$ BEGIN" \
  "  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'trip_status') THEN" \
  "    CREATE TYPE trip_status AS ENUM ('PENDING', 'ACTIVE', 'COMPLETED', 'CANCELLED');" \
  "  END IF;" \
  "END \$\$;" \
  "CREATE TABLE IF NOT EXISTS trips (" \
  "    id UUID PRIMARY KEY," \
  "    passenger_id UUID NOT NULL," \
  "    driver_id UUID," \
  "    pickup TEXT NOT NULL," \
  "    dropoff TEXT NOT NULL," \
  "    status trip_status NOT NULL DEFAULT 'PENDING'," \
  "    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()," \
  "    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()" \
  ");" \
  "CREATE INDEX IF NOT EXISTS idx_trips_passenger_id ON trips(passenger_id);" \
  "ENDSQL" \
  "echo 'trip-service migrations applied successfully'"

echo ""

# ============================================================
# 2. driver-service migrations (Alembic inside container)
# ============================================================
echo -e "${BLUE}→ driver-service migrations (Alembic)${NC}"

DRIVER_INSTANCE=$(get_instance_id "driver-service")
if [[ -z "$DRIVER_INSTANCE" || "$DRIVER_INSTANCE" == "None" ]]; then
  echo -e "${RED}✗ No running driver-service instance found${NC}"; exit 1
fi

DRIVER_NAME="Training-${PROJECT}-${ENV}-driver-service"

# Encode the migration script in base64 to avoid quoting issues in SSM.
# Pipe through tr -d '\n' to produce a single-line string (macOS base64
# wraps at 76 chars by default; Linux base64 -w0 is not portable).
DRIVER_MIGRATION_SCRIPT=$(base64 <<SCRIPT | tr -d '\n'
#!/bin/sh
set -e
ID=\$(sudo docker ps -q --filter name=${DRIVER_NAME})
if [ -z "\$ID" ]; then
  echo "ERROR: container ${DRIVER_NAME} not running"
  exit 1
fi
echo "Running alembic upgrade head in container \$ID..."
sudo docker exec "\$ID" /app/venv/bin/alembic upgrade head
echo "driver-service migrations applied successfully"
SCRIPT
)

run_ssm "driver-service: alembic upgrade head" "$DRIVER_INSTANCE" \
  "echo '${DRIVER_MIGRATION_SCRIPT}' | base64 -d | sh"

echo ""

echo -e "${GREEN}✓ All migrations completed for env=${ENV}${NC}"
