#!/bin/bash
set -euo pipefail

# ============================================================================
# Populate SSM Parameter Store for all services
# ============================================================================
# Reads infrastructure outputs (RDS, SQS, EC2 IPs) and writes all required
# env config to SSM so the SSM deploy document can build .env files on EC2.
#
# Prerequisites:
#   - 01-init-rds-schema.sh must have run successfully (databases must exist)
#   - terragrunt apply done for shared-infra, rds, and all compute modules
#   - aws CLI configured with sufficient permissions
#   - BOT_TOKEN env var set (Telegram bot token)
#   - jq installed
#
# Usage:
#   BOT_TOKEN=<token> ./02-populate-ssm.sh [dev|staging|prod]
#
# Dry run (shows what would be written, no actual put-parameter):
#   DRY_RUN=true BOT_TOKEN=<token> ./02-populate-ssm.sh dev
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
  echo -e "${RED}✗ Invalid environment: '$ENV_RAW'${NC}"
  exit 1
fi

ENV="$ENV_RAW"
PROJECT="drive-ops"
REGION="${AWS_REGION:-us-east-2}"
DRY_RUN="${DRY_RUN:-false}"

TERRAGRUNT_DEV_DIR="$(cd "$(dirname "$0")/../terragrunt/envs/${ENV}" && pwd)"
RDS_INSTANCE="${PROJECT}-${ENV}-postgres"
SECRET_ID="${PROJECT}/${ENV}/rds/credentials"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  Populate SSM — project=${PROJECT}  env=${ENV}${NC}"
echo -e "${BLUE}============================================================${NC}"
[[ "$DRY_RUN" == "true" ]] && echo -e "${YELLOW}  DRY RUN — no parameters will be written${NC}"
echo ""

# --- Validate ---
if [[ -z "${BOT_TOKEN:-}" ]]; then
  echo -e "${RED}✗ BOT_TOKEN env var is required${NC}"
  echo "  Usage: BOT_TOKEN=<token> $0 ${ENV}"
  exit 1
fi
command -v jq >/dev/null 2>&1 || { echo -e "${RED}✗ jq is required${NC}"; exit 1; }
command -v aws >/dev/null 2>&1 || { echo -e "${RED}✗ aws CLI is required${NC}"; exit 1; }

# ============================================================
# Helper: put or print SSM parameter
# ============================================================
put_param() {
  local name="$1"
  local value="$2"
  local type="${3:-String}"          # String | SecureString
  local display="${4:-$value}"       # what to print (masked for secrets)

  if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "  ${CYAN}[DRY RUN]${NC} $name = $display"
    return
  fi

  aws ssm put-parameter \
    --region "$REGION" \
    --name "$name" \
    --value "$value" \
    --type "$type" \
    --overwrite \
    --no-cli-pager \
    --output text > /dev/null

  echo -e "  ${GREEN}✓${NC} $name = $display"
}

# ============================================================
# 1. Fetch infrastructure outputs
# ============================================================
echo -e "${YELLOW}→ Fetching RDS endpoint...${NC}"
RDS_HOST=$(aws rds describe-db-instances \
  --region "$REGION" \
  --db-instance-identifier "$RDS_INSTANCE" \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text)

if [[ -z "$RDS_HOST" || "$RDS_HOST" == "None" ]]; then
  echo -e "${RED}✗ RDS instance '$RDS_INSTANCE' not found${NC}"
  exit 1
fi
echo -e "  ${GREEN}✓${NC} RDS: $RDS_HOST"

echo -e "${YELLOW}→ Fetching RDS credentials from Secrets Manager...${NC}"
SECRET_JSON=$(aws secretsmanager get-secret-value \
  --region "$REGION" \
  --secret-id "$SECRET_ID" \
  --query SecretString \
  --output text)

DB_USER=$(echo "$SECRET_JSON" | jq -r '.username')
DB_PASS=$(echo "$SECRET_JSON" | jq -r '.password')

if [[ -z "$DB_USER" || "$DB_USER" == "null" ]]; then
  echo -e "${RED}✗ 'username' not found in secret '$SECRET_ID'${NC}"; exit 1
fi
if [[ -z "$DB_PASS" || "$DB_PASS" == "null" ]]; then
  echo -e "${RED}✗ 'password' not found in secret '$SECRET_ID'${NC}"; exit 1
fi
# URL-encode the password so special chars (>, %, #, ?, $) don't break the connection string
DB_PASS_ENCODED=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$DB_PASS")
echo -e "  ${GREEN}✓${NC} DB credentials fetched (user=$DB_USER)"

echo -e "${YELLOW}→ Fetching SQS URLs from Terragrunt outputs...${NC}"
SQS_JSON=$(cd "$TERRAGRUNT_DEV_DIR/shared-infra" && terragrunt output -json sqs_urls 2>/dev/null)

SQS_TRIP_CREATED=$(echo    "$SQS_JSON" | jq -r '.trip_created')
SQS_DRIVER_ASSIGNED=$(echo "$SQS_JSON" | jq -r '.driver_assigned')
SQS_TRIP_COMPLETED=$(echo  "$SQS_JSON" | jq -r '.trip_completed')

for var_name in SQS_TRIP_CREATED SQS_DRIVER_ASSIGNED SQS_TRIP_COMPLETED; do
  val="${!var_name}"
  if [[ -z "$val" || "$val" == "null" ]]; then
    echo -e "${RED}✗ Could not read $var_name from shared-infra outputs${NC}"; exit 1
  fi
done
echo -e "  ${GREEN}✓${NC} SQS URLs fetched"

echo -e "${YELLOW}→ Fetching EC2 public IPs by service tag...${NC}"

get_ec2_ip() {
  local service_tag="$1"
  aws ec2 describe-instances \
    --region "$REGION" \
    --filters \
      "Name=tag:Service,Values=$service_tag" \
      "Name=instance-state-name,Values=running" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text
}

TRIP_IP=$(get_ec2_ip "trip-service")
DRIVER_IP=$(get_ec2_ip "driver-service")
GW_IP=$(get_ec2_ip "client-gateway")

for svc_var in TRIP_IP DRIVER_IP GW_IP; do
  val="${!svc_var}"
  if [[ -z "$val" || "$val" == "None" ]]; then
    echo -e "${RED}✗ Running EC2 instance not found for: $svc_var${NC}"
    echo "  Make sure the compute modules were applied and instances are running."
    exit 1
  fi
done

echo -e "  ${GREEN}✓${NC} trip-service    → $TRIP_IP"
echo -e "  ${GREEN}✓${NC} driver-service  → $DRIVER_IP"
echo -e "  ${GREEN}✓${NC} client-gateway  → $GW_IP"
echo ""

# ============================================================
# 2. Build DATABASE_URL strings
# ============================================================
# DB names match init-rds-schema.sh convention
ENV_NORM="${ENV//-/_}"
TRIP_DB_URL="postgresql://${DB_USER}:${DB_PASS_ENCODED}@${RDS_HOST}:5432/drive_ops_${ENV_NORM}_trip?sslmode=require"
DRIVER_DB_URL="postgresql://${DB_USER}:${DB_PASS_ENCODED}@${RDS_HOST}:5432/drive_ops_${ENV_NORM}_driver?sslmode=require"

# ============================================================
# 3. Write SSM parameters
# ============================================================

SSM_BASE="/${PROJECT}/${ENV}"

# ---- trip-service ----
echo -e "${BLUE}→ Writing trip-service parameters...${NC}"
put_param "${SSM_BASE}/trip-service/db-url" "$TRIP_DB_URL" "SecureString" "postgresql://***@${RDS_HOST}/drive_ops_${ENV_NORM}_trip?sslmode=require"

# ---- driver-service ----
echo -e "${BLUE}→ Writing driver-service parameters...${NC}"
put_param "${SSM_BASE}/driver-service/database-url"      "$DRIVER_DB_URL"              "SecureString" "postgresql://***@${RDS_HOST}/drive_ops_${ENV_NORM}_driver?sslmode=require"
put_param "${SSM_BASE}/driver-service/client-gateway-url" "http://${GW_IP}:8080"       "String"

# ---- client-gateway ----
echo -e "${BLUE}→ Writing client-gateway parameters...${NC}"
put_param "${SSM_BASE}/client-gateway/trip-service-url"    "http://${TRIP_IP}:8081"   "String"
put_param "${SSM_BASE}/client-gateway/driver-service-url"  "http://${DRIVER_IP}:8082" "String"
put_param "${SSM_BASE}/client-gateway/bot-token"           "$BOT_TOKEN"               "SecureString" "***"

# ---- shared SQS (all services read these) ----
echo -e "${BLUE}→ Writing shared SQS parameters...${NC}"
put_param "${SSM_BASE}/sqs/sqs-trip-created-url"    "$SQS_TRIP_CREATED"    "String"
put_param "${SSM_BASE}/sqs/sqs-driver-assigned-url" "$SQS_DRIVER_ASSIGNED" "String"
put_param "${SSM_BASE}/sqs/sqs-trip-completed-url"  "$SQS_TRIP_COMPLETED"  "String"

echo ""
echo -e "${GREEN}✓ All SSM parameters populated for env=${ENV}${NC}"
echo ""
echo -e "${YELLOW}Next step:${NC}"
echo "  ./03-deploy-services.sh ${ENV}"
