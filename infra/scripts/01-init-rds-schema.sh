#!/bin/bash
set -euo pipefail

# ============================================================================
# Initialize RDS databases via SSM Run Command
# ============================================================================
# Creates the per-service PostgreSQL databases on RDS by running psql through
# an existing EC2 instance (trip-service preferred, driver-service as fallback).
# Credentials are fetched from Secrets Manager on the EC2 instance itself so
# that RDS never needs to be publicly accessible.
#
# Only databases are created here — table schemas are applied by the
# individual service migrations in 04-run-migrations.sh.
#
# Prerequisites:
#   - Terraform/Terragrunt compute modules applied (EC2 instances must be running)
#   - EC2 instances must have SSM agent active and IAM role with:
#       secretsmanager:GetSecretValue, rds:DescribeDBInstances
#   - Secret "drive-ops/<env>/rds/credentials" must exist in Secrets Manager
#
# Usage:
#   ./01-init-rds-schema.sh [dev|staging|prod]
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

# Derive names used inside the remote script (expanded locally)
ENV_NORM="${ENV//-/_}"
TRIP_DB="drive_ops_${ENV_NORM}_trip"
DRIVER_DB="drive_ops_${ENV_NORM}_driver"
SECRET_ID="${PROJECT}/${ENV}/rds/credentials"
RDS_INSTANCE="${PROJECT}-${ENV}-postgres"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  Init RDS schema — env=${ENV}${NC}"
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
# Find a bastion EC2 instance (prefer trip-service)
# ============================================================
echo -e "${YELLOW}→ Locating EC2 instance...${NC}"

BASTION_INSTANCE=$(get_instance_id "trip-service")
BASTION_SVC="trip-service"

if [[ -z "$BASTION_INSTANCE" || "$BASTION_INSTANCE" == "None" ]]; then
  BASTION_INSTANCE=$(get_instance_id "driver-service")
  BASTION_SVC="driver-service"
fi

if [[ -z "$BASTION_INSTANCE" || "$BASTION_INSTANCE" == "None" ]]; then
  echo -e "${RED}✗ No running instance found (tried trip-service, driver-service)${NC}"
  exit 1
fi

echo -e "  ${GREEN}✓${NC} Using ${BASTION_SVC} instance: ${CYAN}${BASTION_INSTANCE}${NC}"
echo ""

# ============================================================
# Build the init script (base64-encoded to avoid quoting issues)
# Variables expanded locally: SECRET_ID, REGION, RDS_INSTANCE,
#                             TRIP_DB, DRIVER_DB
# Variables escaped with \$:  runtime values on the EC2 instance
# ============================================================
INIT_SCRIPT=$(base64 <<SCRIPT | tr -d '\n'
#!/bin/sh
set -e

# Install psql if missing (Amazon Linux 2 / Ubuntu)
if ! command -v psql >/dev/null 2>&1; then
  echo "psql not found — installing postgresql-client..."
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq && apt-get install -y -qq postgresql-client
  elif command -v yum >/dev/null 2>&1; then
    yum install -y postgresql
  else
    echo "ERROR: cannot install psql — unsupported package manager"; exit 1
  fi
fi

# Fetch credentials from Secrets Manager
echo "Fetching credentials from Secrets Manager..."
SECRET=\$(aws secretsmanager get-secret-value \
  --secret-id "${SECRET_ID}" \
  --region "${REGION}" \
  --query SecretString \
  --output text)

DB_USER=\$(echo "\$SECRET" | python3 -c "import sys,json; print(json.load(sys.stdin)['username'])")
DB_PASS=\$(echo "\$SECRET" | python3 -c "import sys,json; print(json.load(sys.stdin)['password'])")

# Fetch RDS endpoint
echo "Fetching RDS endpoint..."
DB_HOST=\$(aws rds describe-db-instances \
  --db-instance-identifier "${RDS_INSTANCE}" \
  --region "${REGION}" \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text)

if [ -z "\$DB_HOST" ] || [ "\$DB_HOST" = "None" ]; then
  echo "ERROR: RDS instance '${RDS_INSTANCE}' not found"; exit 1
fi
echo "RDS host: \$DB_HOST"

# Create databases (idempotent — skips if already exists)
echo "Creating databases..."
PGPASSWORD="\$DB_PASS" psql -v ON_ERROR_STOP=1 \
  -h "\$DB_HOST" -U "\$DB_USER" -d postgres <<SQL
SELECT 'CREATE DATABASE ${TRIP_DB}'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${TRIP_DB}')\gexec
SELECT 'CREATE DATABASE ${DRIVER_DB}'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DRIVER_DB}')\gexec
SQL

echo "Done: databases '${TRIP_DB}' and '${DRIVER_DB}' are ready."
SCRIPT
)

# ============================================================
# Run via SSM
# ============================================================
run_ssm "init-rds-schema: create databases" "$BASTION_INSTANCE" \
  "echo '${INIT_SCRIPT}' | base64 -d | sh"

echo ""
echo -e "${GREEN}✓ RDS schema initialised for env=${ENV}${NC}"
echo ""
echo -e "${YELLOW}Next step:${NC}"
echo "  ./02-populate-ssm.sh ${ENV}"
