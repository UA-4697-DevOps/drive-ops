#!/bin/bash
set -euo pipefail

# ============================================================================
# Deploy all services via SSM Run Command
# ============================================================================
# Triggers the SSM deploy document on each EC2 instance.
# The document: logs into ECR, reads SSM params → .env, runs docker run.
#
# Prerequisites:
#   - 02-populate-ssm.sh must have run successfully
#   - EC2 instances must be running with SSM agent active
#   - IAM roles must have ssm:SendCommand permission
#
# Usage:
#   ./03-deploy-services.sh [dev|staging|prod] [image-tag] [service]
#
# Examples:
#   ./03-deploy-services.sh dev latest                        # all services
#   ./03-deploy-services.sh dev sha-d14c08b trip-service      # one service
#   ./03-deploy-services.sh dev sha-d14c08b driver-service
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
IMAGE_TAG="${2:-latest}"

if [[ ! "$ENV_RAW" =~ ^[a-z0-9_-]+$ ]]; then
  echo -e "${RED}✗ Invalid environment: '$ENV_RAW'${NC}"; exit 1
fi

ENV="$ENV_RAW"
PROJECT="drive-ops"
REGION="${AWS_REGION:-us-east-2}"
SERVICE_FILTER="${3:-}"   # optional: trip-service | driver-service | client-gateway
POLL_INTERVAL=5           # seconds between status checks
TIMEOUT=300               # max seconds to wait per service

# SSM document names follow the compute module naming: Training-{project}-{env}-{service}-deploy
TRIP_DOC="Training-${PROJECT}-${ENV}-trip-service-deploy"
DRIVER_DOC="Training-${PROJECT}-${ENV}-driver-service-deploy"
GW_DOC="Training-${PROJECT}-${ENV}-client-gateway-deploy"

if [[ -n "$SERVICE_FILTER" ]]; then
  echo -e "${BLUE}============================================================${NC}"
  echo -e "${BLUE}  Deploy ${SERVICE_FILTER} — env=${ENV}  tag=${IMAGE_TAG}${NC}"
  echo -e "${BLUE}============================================================${NC}"
else
  echo -e "${BLUE}============================================================${NC}"
  echo -e "${BLUE}  Deploy all services — env=${ENV}  tag=${IMAGE_TAG}${NC}"
  echo -e "${BLUE}============================================================${NC}"
fi
echo ""

# ============================================================
# Helper: get running instance ID by service tag
# ============================================================
get_instance_id() {
  local service_tag="$1"
  aws ec2 describe-instances \
    --region "$REGION" \
    --filters \
      "Name=tag:Service,Values=$service_tag" \
      "Name=instance-state-name,Values=running" \
    --query 'Reservations[0].Instances[0].InstanceId' \
    --output text
}

# ============================================================
# Helper: send SSM command and wait for result
# ============================================================
deploy_service() {
  local service_label="$1"   # human-readable name
  local doc_name="$2"        # SSM document name
  local instance_id="$3"     # EC2 instance ID

  echo -e "${YELLOW}→ Deploying ${service_label} (${instance_id})...${NC}"

  COMMAND_ID=$(aws ssm send-command \
    --region "$REGION" \
    --document-name "$doc_name" \
    --instance-ids "$instance_id" \
    --parameters "ImageTag=${IMAGE_TAG}" \
    --comment "Deploy ${service_label} tag=${IMAGE_TAG}" \
    --query 'Command.CommandId' \
    --output text)

  echo -e "  Command ID: ${CYAN}${COMMAND_ID}${NC}"

  # Poll until done or timeout
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
        echo -e "  ${GREEN}✓ ${service_label} deployed successfully${NC}"
        return 0
        ;;
      Failed|Cancelled|TimedOut|Undeliverable|Terminated)
        echo -e "  ${RED}✗ ${service_label} deploy FAILED (status: $STATUS)${NC}"
        echo -e "  ${YELLOW}→ Fetching error output...${NC}"
        aws ssm get-command-invocation \
          --region "$REGION" \
          --command-id "$COMMAND_ID" \
          --instance-id "$instance_id" \
          --query 'StandardErrorContent' \
          --output text 2>/dev/null | tail -30 | sed 's/^/    /'
        return 1
        ;;
      *)
        if (( elapsed >= TIMEOUT )); then
          echo -e "  ${RED}✗ Timed out after ${TIMEOUT}s waiting for ${service_label}${NC}"
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
# Build list of services to deploy
# ============================================================
# Each entry: "service-tag:ssm-doc"
ALL_SERVICES=(
  "trip-service:$TRIP_DOC"
  "driver-service:$DRIVER_DOC"
  "client-gateway:$GW_DOC"
)

SERVICES=()
for entry in "${ALL_SERVICES[@]}"; do
  svc="${entry%%:*}"
  if [[ -z "$SERVICE_FILTER" || "$SERVICE_FILTER" == "$svc" ]]; then
    SERVICES+=("$entry")
  fi
done

if [[ ${#SERVICES[@]} -eq 0 ]]; then
  echo -e "${RED}✗ Unknown service: '$SERVICE_FILTER'${NC}"
  echo "  Valid values: trip-service, driver-service, client-gateway"
  exit 1
fi

# ============================================================
# 1. Resolve instance IDs — stored as third field: svc:doc:iid
# ============================================================
echo -e "${YELLOW}→ Resolving EC2 instance IDs...${NC}"

RESOLVED=()
for entry in "${SERVICES[@]}"; do
  svc="${entry%%:*}"
  doc="${entry##*:}"
  iid=$(get_instance_id "$svc")
  if [[ -z "$iid" || "$iid" == "None" ]]; then
    echo -e "${RED}✗ No running EC2 found for service tag: $svc${NC}"; exit 1
  fi
  RESOLVED+=("${svc}:${doc}:${iid}")
  echo -e "  ${GREEN}✓${NC} $svc → $iid"
done
echo ""

# ============================================================
# 2. Verify SSM documents exist
# ============================================================
echo -e "${YELLOW}→ Verifying SSM documents exist...${NC}"
for entry in "${RESOLVED[@]}"; do
  svc="${entry%%:*}"
  rest="${entry#*:}"
  doc="${rest%%:*}"
  STATUS=$(aws ssm describe-document \
    --region "$REGION" \
    --name "$doc" \
    --query 'Document.Status' \
    --output text 2>/dev/null || echo "NOT_FOUND")
  if [[ "$STATUS" != "Active" ]]; then
    echo -e "${RED}✗ SSM document not found or not active: $doc${NC}"
    echo "  Run: terragrunt apply in the corresponding compute module"
    exit 1
  fi
  echo -e "  ${GREEN}✓${NC} $doc"
done
echo ""

# ============================================================
# 3. Deploy
# ============================================================
FAILED=0

for entry in "${RESOLVED[@]}"; do
  svc="${entry%%:*}"
  rest="${entry#*:}"
  doc="${rest%%:*}"
  iid="${rest##*:}"
  deploy_service "$svc" "$doc" "$iid" || FAILED=$((FAILED + 1))
  echo ""
done

# ============================================================
# 4. Summary
# ============================================================
if (( FAILED == 0 )); then
  echo -e "${GREEN}✓ All services deployed successfully (tag=${IMAGE_TAG})${NC}"
  echo ""
  echo -e "${YELLOW}Health checks:${NC}"

  # Fetch IPs for health check output
  get_ec2_ip() {
    aws ec2 describe-instances \
      --region "$REGION" \
      --filters "Name=tag:Service,Values=$1" "Name=instance-state-name,Values=running" \
      --query 'Reservations[0].Instances[0].PublicIpAddress' \
      --output text
  }

  TRIP_IP=$(get_ec2_ip "trip-service")
  DRIVER_IP=$(get_ec2_ip "driver-service")
  GW_IP=$(get_ec2_ip "client-gateway")

  echo "  curl http://${TRIP_IP}:8081/health"
  echo "  curl http://${DRIVER_IP}:8082/health"
  echo "  curl http://${GW_IP}:8080/health"
else
  echo -e "${RED}✗ ${FAILED} service(s) failed to deploy${NC}"
  echo "  Check SSM Run Command history in AWS console for details."
  exit 1
fi
