#!/bin/bash
set -euo pipefail

# ============================================================================
# populate-ingress-values.sh
# ============================================================================
# Reads live Terraform state via terragrunt output and patches all public-
# facing Ingress manifests with real infrastructure values:
#
#   • alb.ingress.kubernetes.io/certificate-arn  (from dev/acm)
#   • alb.ingress.kubernetes.io/subnets          (from dev/shared-infra)
#   • alb.ingress.kubernetes.io/security-groups  (from dev/shared-infra)
#
# Run this script once after `terragrunt apply` in the acm and shared-infra
# modules, then commit the updated manifests.
#
# Prerequisites:
#   - terragrunt installed and in PATH
#   - jq installed and in PATH
#   - AWS credentials configured (same profile used by terragrunt)
#   - Terraform state must already exist for dev/acm and dev/shared-infra
#
# Usage:
#   ./infra/scripts/populate-ingress-values.sh [dev|staging|prod]
#
# Example:
#   ./infra/scripts/populate-ingress-values.sh dev
# ============================================================================

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- Paths ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

ENV="${1:-dev}"

TG_ACM_DIR="${REPO_ROOT}/infra/terragrunt/envs/${ENV}/acm"
TG_SHARED_DIR="${REPO_ROOT}/infra/terragrunt/envs/${ENV}/shared-infra"

# Manifests to patch — add more here as new public Ingresses are introduced
INGRESS_FILES=(
  "${REPO_ROOT}/infra/k8s/apps/client-gateway/ingress.yaml"
  "${REPO_ROOT}/infra/k8s/apps/web-client/ingress.yaml"
)

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  Populate Ingress values — env=${ENV}${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# ============================================================
# Validate deps
# ============================================================
for cmd in terragrunt jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo -e "${RED}✗ Required command not found: ${cmd}${NC}"
    exit 1
  fi
done

# ============================================================
# Validate dirs
# ============================================================
for dir in "$TG_ACM_DIR" "$TG_SHARED_DIR"; do
  if [[ ! -d "$dir" ]]; then
    echo -e "${RED}✗ Terragrunt env directory not found: ${dir}${NC}"
    echo "  Only 'dev' is fully wired. For other envs, add a terragrunt.hcl first."
    exit 1
  fi
done

# ============================================================
# 1. Read ACM certificate ARN
# ============================================================
echo -e "${YELLOW}→ Reading certificate_arn from ${ENV}/acm...${NC}"
CERT_ARN=$(cd "$TG_ACM_DIR" && terragrunt output -raw certificate_arn 2>/dev/null)

if [[ -z "$CERT_ARN" ]]; then
  echo -e "${RED}✗ certificate_arn is empty. Has 'terragrunt apply' been run in ${ENV}/acm?${NC}"
  exit 1
fi
echo -e "  ${GREEN}✓${NC} certificate_arn = ${CYAN}${CERT_ARN}${NC}"
echo ""

# ============================================================
# 2. Read public subnet IDs (returned as JSON array, need CSV)
# ============================================================
echo -e "${YELLOW}→ Reading public_subnet_ids from ${ENV}/shared-infra...${NC}"
SUBNET_JSON=$(cd "$TG_SHARED_DIR" && terragrunt output -json public_subnet_ids 2>/dev/null)
SUBNET_IDS=$(echo "$SUBNET_JSON" | jq -r '[.[]] | join(",")')

if [[ -z "$SUBNET_IDS" ]]; then
  echo -e "${RED}✗ public_subnet_ids is empty. Has 'terragrunt apply' been run in ${ENV}/shared-infra?${NC}"
  exit 1
fi
echo -e "  ${GREEN}✓${NC} public_subnet_ids = ${CYAN}${SUBNET_IDS}${NC}"

# ============================================================
# 3. Read ALB security group ID
# ============================================================
echo -e "${YELLOW}→ Reading sg_alb_id from ${ENV}/shared-infra...${NC}"
ALB_SG=$(cd "$TG_SHARED_DIR" && terragrunt output -raw sg_alb_id 2>/dev/null)

if [[ -z "$ALB_SG" ]]; then
  echo -e "${RED}✗ sg_alb_id is empty. Has 'terragrunt apply' been run in ${ENV}/shared-infra?${NC}"
  exit 1
fi
echo -e "  ${GREEN}✓${NC} sg_alb_id = ${CYAN}${ALB_SG}${NC}"
echo ""

# ============================================================
# 4. Patch manifests
# ============================================================
echo -e "${YELLOW}→ Patching Ingress manifests...${NC}"

for manifest in "${INGRESS_FILES[@]}"; do
  if [[ ! -f "$manifest" ]]; then
    echo -e "  ${YELLOW}⚠ Skipping (not found): ${manifest}${NC}"
    continue
  fi

  # Use a temp file to apply all three substitutions atomically
  TMP=$(mktemp)
  sed \
    -e "s|REPLACE_WITH_ACM_CERT_ARN|${CERT_ARN}|g" \
    -e "s|REPLACE_WITH_PUBLIC_SUBNET_IDS|${SUBNET_IDS}|g" \
    -e "s|REPLACE_WITH_ALB_SG_ID|${ALB_SG}|g" \
    "$manifest" > "$TMP"
  mv "$TMP" "$manifest"

  REL_PATH="${manifest#${REPO_ROOT}/}"
  echo -e "  ${GREEN}✓${NC} Patched: ${REL_PATH}"
done

echo ""
echo -e "${GREEN}✓ All Ingress manifests populated (env=${ENV})${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Review the diffs:  git diff infra/k8s/apps/"
echo "  2. Commit the changes: git add infra/k8s/apps/ && git commit -m 'chore: populate ALB ingress values for ${ENV}'"
echo "  3. ArgoCD will sync the changes automatically, or run: kubectl apply -k infra/k8s/apps/"
echo ""
echo -e "${YELLOW}Smoke-test HTTPS after ALB is provisioned:${NC}"
echo "  curl -Iv http://driveops.dmytrominochkin.cloud        # expect 301 → HTTPS"
echo "  curl -Iv https://driveops.dmytrominochkin.cloud       # expect 200 OK"
echo "  curl -Iv http://api.driveops.dmytrominochkin.cloud    # expect 301 → HTTPS"
echo "  curl -Iv https://api.driveops.dmytrominochkin.cloud/health  # expect 200 OK"
