#!/bin/bash
set -euo pipefail

# ============================================================================
# populate-infra-values.sh
# ============================================================================
# Reads live Terraform state via terragrunt output and patches all public-
# facing Ingress manifests AND ArgoCD Application manifests with real
# infrastructure values:
#
#   Ingress manifests:
#   • alb.ingress.kubernetes.io/certificate-arn  (from dev/acm)
#   • alb.ingress.kubernetes.io/subnets          (from dev/shared-infra)
#   • alb.ingress.kubernetes.io/security-groups  (from dev/shared-infra)
#
#   ArgoCD Applications:
#   • AWS LB Controller: clusterName, eks.amazonaws.com/role-arn, vpcId
#   • External DNS: eks.amazonaws.com/role-arn
#
# Run this script once after `terragrunt apply` in the acm, shared-infra,
# eks, aws-lb-controller, and external-dns modules, then commit the updated
# manifests.
#
# Prerequisites:
#   - terragrunt installed and in PATH
#   - jq installed and in PATH
#   - AWS credentials configured (same profile used by terragrunt)
#   - Terraform state must already exist for the queried modules
#
# Usage:
#   ./infra/scripts/populate-infra-values.sh [dev|staging|prod]
#
# Example:
#   ./infra/scripts/populate-infra-values.sh dev
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
TG_EKS_DIR="${REPO_ROOT}/infra/terragrunt/envs/${ENV}/eks"
TG_ALB_DIR="${REPO_ROOT}/infra/terragrunt/envs/${ENV}/aws-lb-controller"
TG_EDNS_DIR="${REPO_ROOT}/infra/terragrunt/envs/${ENV}/external-dns"
TG_CM_DIR="${REPO_ROOT}/infra/terragrunt/envs/${ENV}/cert-manager"

# Manifests to patch — add more here as new public Ingresses are introduced
INGRESS_FILES=(
  "${REPO_ROOT}/infra/k8s/apps/client-gateway/ingress.yaml"
  "${REPO_ROOT}/infra/k8s/apps/web-client/ingress.yaml"
)

# ArgoCD Application manifests to patch
ALB_CONTROLLER_APP="${REPO_ROOT}/infra/k8s/apps/aws-lb-controller.yaml"
EXTERNAL_DNS_APP="${REPO_ROOT}/infra/k8s/apps/external-dns.yaml"
CERT_MANAGER_APP="${REPO_ROOT}/infra/k8s/apps/cert-manager.yaml"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  Populate infrastructure values — env=${ENV}${NC}"
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
for dir in "$TG_ACM_DIR" "$TG_SHARED_DIR" "$TG_EKS_DIR" "$TG_ALB_DIR" "$TG_EDNS_DIR" "$TG_CM_DIR"; do
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
CERT_OUTPUT=$(mktemp)
cd "$TG_ACM_DIR" && terragrunt output -raw certificate_arn > "$CERT_OUTPUT" 2>&1
CERT_EXIT=$?
if [[ $CERT_EXIT -ne 0 ]]; then
  CERT_ERR=$(cat "$CERT_OUTPUT")
  echo -e "${RED}✗ Failed to read certificate_arn from ${ENV}/acm (exit code: $CERT_EXIT)${NC}"
  echo -e "${RED}   Error: ${CERT_ERR}${NC}"
  rm -f "$CERT_OUTPUT"
  exit $CERT_EXIT
fi
CERT_ARN=$(cat "$CERT_OUTPUT")
rm -f "$CERT_OUTPUT"

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
SUBNET_OUTPUT=$(mktemp)
cd "$TG_SHARED_DIR" && terragrunt output -json public_subnet_ids > "$SUBNET_OUTPUT" 2>&1
SUBNET_EXIT=$?
if [[ $SUBNET_EXIT -ne 0 ]]; then
  SUBNET_ERR=$(cat "$SUBNET_OUTPUT")
  echo -e "${RED}✗ Failed to read public_subnet_ids from ${ENV}/shared-infra (exit code: $SUBNET_EXIT)${NC}"
  echo -e "${RED}   Error: ${SUBNET_ERR}${NC}"
  rm -f "$SUBNET_OUTPUT"
  exit $SUBNET_EXIT
fi
SUBNET_JSON=$(cat "$SUBNET_OUTPUT")
rm -f "$SUBNET_OUTPUT"
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
ALB_OUTPUT=$(mktemp)
cd "$TG_SHARED_DIR" && terragrunt output -raw sg_alb_id > "$ALB_OUTPUT" 2>&1
ALB_EXIT=$?
if [[ $ALB_EXIT -ne 0 ]]; then
  ALB_ERR=$(cat "$ALB_OUTPUT")
  echo -e "${RED}✗ Failed to read sg_alb_id from ${ENV}/shared-infra (exit code: $ALB_EXIT)${NC}"
  echo -e "${RED}   Error: ${ALB_ERR}${NC}"
  rm -f "$ALB_OUTPUT"
  exit $ALB_EXIT
fi
ALB_SG=$(cat "$ALB_OUTPUT")
rm -f "$ALB_OUTPUT"

if [[ -z "$ALB_SG" ]]; then
  echo -e "${RED}✗ sg_alb_id is empty. Has 'terragrunt apply' been run in ${ENV}/shared-infra?${NC}"
  exit 1
fi
echo -e "  ${GREEN}✓${NC} sg_alb_id = ${CYAN}${ALB_SG}${NC}"
echo ""

# ============================================================
# 4. Read EKS cluster name
# ============================================================
echo -e "${YELLOW}→ Reading cluster_name from ${ENV}/eks...${NC}"
CLUSTER_OUTPUT=$(mktemp)
cd "$TG_EKS_DIR" && terragrunt output -raw cluster_name > "$CLUSTER_OUTPUT" 2>&1
CLUSTER_EXIT=$?
if [[ $CLUSTER_EXIT -ne 0 ]]; then
  CLUSTER_ERR=$(cat "$CLUSTER_OUTPUT")
  echo -e "${RED}✗ Failed to read cluster_name from ${ENV}/eks (exit code: $CLUSTER_EXIT)${NC}"
  echo -e "${RED}   Error: ${CLUSTER_ERR}${NC}"
  rm -f "$CLUSTER_OUTPUT"
  exit $CLUSTER_EXIT
fi
CLUSTER_NAME=$(cat "$CLUSTER_OUTPUT")
rm -f "$CLUSTER_OUTPUT"

if [[ -z "$CLUSTER_NAME" ]]; then
  echo -e "${RED}✗ cluster_name is empty. Has 'terragrunt apply' been run in ${ENV}/eks?${NC}"
  exit 1
fi
echo -e "  ${GREEN}✓${NC} cluster_name = ${CYAN}${CLUSTER_NAME}${NC}"

# ============================================================
# 5. Read VPC ID
# ============================================================
echo -e "${YELLOW}→ Reading vpc_id from ${ENV}/shared-infra...${NC}"
VPC_OUTPUT=$(mktemp)
cd "$TG_SHARED_DIR" && terragrunt output -raw vpc_id > "$VPC_OUTPUT" 2>&1
VPC_EXIT=$?
if [[ $VPC_EXIT -ne 0 ]]; then
  VPC_ERR=$(cat "$VPC_OUTPUT")
  echo -e "${RED}✗ Failed to read vpc_id from ${ENV}/shared-infra (exit code: $VPC_EXIT)${NC}"
  echo -e "${RED}   Error: ${VPC_ERR}${NC}"
  rm -f "$VPC_OUTPUT"
  exit $VPC_EXIT
fi
VPC_ID=$(cat "$VPC_OUTPUT")
rm -f "$VPC_OUTPUT"

if [[ -z "$VPC_ID" ]]; then
  echo -e "${RED}✗ vpc_id is empty. Has 'terragrunt apply' been run in ${ENV}/shared-infra?${NC}"
  exit 1
fi
echo -e "  ${GREEN}✓${NC} vpc_id = ${CYAN}${VPC_ID}${NC}"

# ============================================================
# 6. Read ALB Controller IAM Role ARN
# ============================================================
echo -e "${YELLOW}→ Reading alb_controller_role_arn from ${ENV}/aws-lb-controller...${NC}"
ALB_ROLE_OUTPUT=$(mktemp)
cd "$TG_ALB_DIR" && terragrunt output -raw alb_controller_role_arn > "$ALB_ROLE_OUTPUT" 2>&1
ALB_ROLE_EXIT=$?
if [[ $ALB_ROLE_EXIT -ne 0 ]]; then
  ALB_ROLE_ERR=$(cat "$ALB_ROLE_OUTPUT")
  echo -e "${RED}✗ Failed to read alb_controller_role_arn from ${ENV}/aws-lb-controller (exit code: $ALB_ROLE_EXIT)${NC}"
  echo -e "${RED}   Error: ${ALB_ROLE_ERR}${NC}"
  rm -f "$ALB_ROLE_OUTPUT"
  exit $ALB_ROLE_EXIT
fi
ALB_ROLE_ARN=$(cat "$ALB_ROLE_OUTPUT")
rm -f "$ALB_ROLE_OUTPUT"

if [[ -z "$ALB_ROLE_ARN" ]]; then
  echo -e "${RED}✗ alb_controller_role_arn is empty. Has 'terragrunt apply' been run in ${ENV}/aws-lb-controller?${NC}"
  exit 1
fi
echo -e "  ${GREEN}✓${NC} alb_controller_role_arn = ${CYAN}${ALB_ROLE_ARN}${NC}"

# ============================================================
# 7. Read External DNS IAM Role ARN
# ============================================================
echo -e "${YELLOW}→ Reading external_dns_role_arn from ${ENV}/external-dns...${NC}"
EDNS_ROLE_OUTPUT=$(mktemp)
cd "$TG_EDNS_DIR" && terragrunt output -raw external_dns_role_arn > "$EDNS_ROLE_OUTPUT" 2>&1
EDNS_ROLE_EXIT=$?
if [[ $EDNS_ROLE_EXIT -ne 0 ]]; then
  EDNS_ROLE_ERR=$(cat "$EDNS_ROLE_OUTPUT")
  echo -e "${RED}✗ Failed to read external_dns_role_arn from ${ENV}/external-dns (exit code: $EDNS_ROLE_EXIT)${NC}"
  echo -e "${RED}   Error: ${EDNS_ROLE_ERR}${NC}"
  rm -f "$EDNS_ROLE_OUTPUT"
  exit $EDNS_ROLE_EXIT
fi
EDNS_ROLE_ARN=$(cat "$EDNS_ROLE_OUTPUT")
rm -f "$EDNS_ROLE_OUTPUT"

if [[ -z "$EDNS_ROLE_ARN" ]]; then
  echo -e "${RED}✗ external_dns_role_arn is empty. Has 'terragrunt apply' been run in ${ENV}/external-dns?${NC}"
  exit 1
fi
echo -e "  ${GREEN}✓${NC} external_dns_role_arn = ${CYAN}${EDNS_ROLE_ARN}${NC}"

# ============================================================
# 8. Read cert-manager IAM Role ARN
# ============================================================
echo -e "${YELLOW}→ Reading cert_manager_role_arn from ${ENV}/cert-manager...${NC}"
CM_ROLE_OUTPUT=$(mktemp)
cd "$TG_CM_DIR" && terragrunt output -raw cert_manager_role_arn > "$CM_ROLE_OUTPUT" 2>&1
CM_ROLE_EXIT=$?
if [[ $CM_ROLE_EXIT -ne 0 ]]; then
  CM_ROLE_ERR=$(cat "$CM_ROLE_OUTPUT")
  echo -e "${RED}✗ Failed to read cert_manager_role_arn from ${ENV}/cert-manager (exit code: $CM_ROLE_EXIT)${NC}"
  echo -e "${RED}   Error: ${CM_ROLE_ERR}${NC}"
  rm -f "$CM_ROLE_OUTPUT"
  exit $CM_ROLE_EXIT
fi
CM_ROLE_ARN=$(cat "$CM_ROLE_OUTPUT")
rm -f "$CM_ROLE_OUTPUT"

if [[ -z "$CM_ROLE_ARN" ]]; then
  echo -e "${RED}✗ cert_manager_role_arn is empty. Has 'terragrunt apply' been run in ${ENV}/cert-manager?${NC}"
  exit 1
fi
echo -e "  ${GREEN}✓${NC} cert_manager_role_arn = ${CYAN}${CM_ROLE_ARN}${NC}"
echo ""

# ============================================================
# 9. Patch Ingress manifests
# ============================================================
echo -e "${YELLOW}→ Patching Ingress manifests...${NC}"

for manifest in "${INGRESS_FILES[@]}"; do
  if [[ ! -f "$manifest" ]]; then
    echo -e "  ${YELLOW}⚠ Skipping (not found): ${manifest}${NC}"
    continue
  fi

  # Use a temp file to apply all three substitutions atomically.
  # Use regexes to match the entire annotation line, making replacements idempotent
  # (i.e., subsequent runs will re-replace actual values, not just placeholders).
  TMP=$(mktemp)
  sed \
    -e "s#\(alb.ingress.kubernetes.io/certificate-arn:\).*#\1 ${CERT_ARN} # From acm output: certificate_arn#" \
    -e "s#\(alb.ingress.kubernetes.io/subnets:\).*#\1 ${SUBNET_IDS} # From shared-infra output: public_subnet_ids (comma-separated)#" \
    -e "s#\(alb.ingress.kubernetes.io/security-groups:\).*#\1 ${ALB_SG} # From shared-infra output: sg_alb_id#" \
    "$manifest" > "$TMP"
  mv "$TMP" "$manifest"

  REL_PATH="${manifest#${REPO_ROOT}/}"
  echo -e "  ${GREEN}✓${NC} Patched: ${REL_PATH}"
done

echo ""
echo -e "${GREEN}✓ All Ingress manifests populated (env=${ENV})${NC}"
echo ""

# ============================================================
# 10. Patch AWS Load Balancer Controller ArgoCD Application
# ============================================================
echo -e "${YELLOW}→ Patching AWS LB Controller manifest...${NC}"
if [[ -f "$ALB_CONTROLLER_APP" ]]; then
  TMP=$(mktemp)
  sed \
    -e "s#\(clusterName:\).*#\1 ${CLUSTER_NAME} # From eks output: cluster_name#" \
    -e "s#\(eks.amazonaws.com/role-arn:\).*alb.*#eks.amazonaws.com/role-arn: ${ALB_ROLE_ARN} # From aws-lb-controller output: alb_controller_role_arn#" \
    -e "s#\(vpcId:\).*#\1 ${VPC_ID} # From shared-infra output: vpc_id#" \
    "$ALB_CONTROLLER_APP" > "$TMP"
  mv "$TMP" "$ALB_CONTROLLER_APP"
  REL_PATH="${ALB_CONTROLLER_APP#${REPO_ROOT}/}"
  echo -e "  ${GREEN}✓${NC} Patched: ${REL_PATH}"
else
  echo -e "  ${YELLOW}⚠ Skipping (not found): ${ALB_CONTROLLER_APP}${NC}"
fi

# ============================================================
# 11. Patch External DNS ArgoCD Application
# ============================================================
echo -e "${YELLOW}→ Patching External DNS manifest...${NC}"
if [[ -f "$EXTERNAL_DNS_APP" ]]; then
  TMP=$(mktemp)
  sed \
    -e "s#\(eks.amazonaws.com/role-arn:\).*#\1 ${EDNS_ROLE_ARN} # From external-dns output: external_dns_role_arn#" \
    "$EXTERNAL_DNS_APP" > "$TMP"
  mv "$TMP" "$EXTERNAL_DNS_APP"
  REL_PATH="${EXTERNAL_DNS_APP#${REPO_ROOT}/}"
  echo -e "  ${GREEN}✓${NC} Patched: ${REL_PATH}"
else
  echo -e "  ${YELLOW}⚠ Skipping (not found): ${EXTERNAL_DNS_APP}${NC}"
fi

# ============================================================
# 12. Patch cert-manager ArgoCD Application
# ============================================================
echo -e "${YELLOW}→ Patching cert-manager manifest...${NC}"
if [[ -f "$CERT_MANAGER_APP" ]]; then
  TMP=$(mktemp)
  sed \
    -e "s#\(eks.amazonaws.com/role-arn:\).*#\1 ${CM_ROLE_ARN} # From cert-manager output: cert_manager_role_arn#" \
    "$CERT_MANAGER_APP" > "$TMP"
  mv "$TMP" "$CERT_MANAGER_APP"
  REL_PATH="${CERT_MANAGER_APP#${REPO_ROOT}/}"
  echo -e "  ${GREEN}✓${NC} Patched: ${REL_PATH}"
else
  echo -e "  ${YELLOW}⚠ Skipping (not found): ${CERT_MANAGER_APP}${NC}"
fi

echo ""
echo -e "${GREEN}✓ All infrastructure values populated (env=${ENV})${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Review the diffs:  git diff infra/k8s/apps/"
echo "  2. Commit the changes: git add infra/k8s/apps/ && git commit -m 'chore: populate infrastructure values for ${ENV}'"
echo "  3. ArgoCD will sync the changes automatically, or run: kubectl apply -k infra/k8s/apps/"
echo ""
echo -e "${YELLOW}Smoke-test HTTPS after ALB is provisioned:${NC}"
echo "  curl -Iv http://driveops.dmytrominochkin.cloud        # expect 301 → HTTPS"
echo "  curl -Iv https://driveops.dmytrominochkin.cloud       # expect 200 OK"
echo "  curl -Iv http://api.driveops.dmytrominochkin.cloud    # expect 301 → HTTPS"
echo "  curl -Iv https://api.driveops.dmytrominochkin.cloud/health  # expect 200 OK"
