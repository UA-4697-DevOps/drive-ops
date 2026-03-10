#!/bin/bash
# ==============================================================================
# POPULATE KUBERNETES PLACEHOLDERS SCRIPT
# ==============================================================================
# This script replaces placeholder values in Kubernetes manifests with actual
# values from Terraform outputs after infrastructure is deployed.
#
# Usage:
#   ./infra/scripts/populate-k8s-placeholders.sh
#
# Prerequisites:
#   - Terraform/Terragrunt infrastructure must be applied
#   - Run from repository root directory
# ==============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Kubernetes Placeholder Replacement${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Check we're in the right directory
if [ ! -d "infra/terragrunt/envs/dev" ]; then
  echo -e "${RED}Error: Must run from repository root${NC}"
  exit 1
fi

# Navigate to terragrunt directory
cd infra/terragrunt/envs/dev

echo -e "${YELLOW}Gathering Terraform outputs...${NC}"
echo ""

# === EKS Outputs ===
echo "  - EKS cluster name..."
CLUSTER_NAME=$(terragrunt output --terragrunt-working-dir=eks cluster_name 2>/dev/null | tr -d '"')

# === VPC/Network Outputs ===
echo "  - VPC ID..."
VPC_ID=$(terragrunt output --terragrunt-working-dir=shared-infra vpc_id 2>/dev/null | tr -d '"')

echo "  - Public subnet IDs..."
PUBLIC_SUBNETS=$(terragrunt output --terragrunt-working-dir=shared-infra public_subnet_ids 2>/dev/null | jq -r 'join(",")')

echo "  - ALB security group ID..."
ALB_SG_ID=$(terragrunt output --terragrunt-working-dir=shared-infra sg_alb_id 2>/dev/null | tr -d '"')

# === IAM Role ARNs ===
echo "  - AWS Load Balancer Controller role ARN..."
ALB_ROLE_ARN=$(terragrunt output --terragrunt-working-dir=aws-lb-controller alb_controller_role_arn 2>/dev/null | tr -d '"')

echo "  - External DNS role ARN..."
EXTERNAL_DNS_ROLE_ARN=$(terragrunt output --terragrunt-working-dir=external-dns external_dns_role_arn 2>/dev/null | tr -d '"')

echo "  - External Secrets Operator role ARN..."
ESO_ROLE_ARN=$(terragrunt output --terragrunt-working-dir=external-secrets eso_role_arn 2>/dev/null | tr -d '"')

echo "  - Cluster Autoscaler role ARN..."
CLUSTER_AUTOSCALER_ROLE_ARN=$(terragrunt output --terragrunt-working-dir=cluster-autoscaler cluster_autoscaler_role_arn 2>/dev/null | tr -d '"')

# === ACM Certificate ===
echo "  - ACM certificate ARN..."
CERT_ARN=$(terragrunt output --terragrunt-working-dir=acm certificate_arn 2>/dev/null | tr -d '"')

echo ""
echo -e "${GREEN}✓ All Terraform outputs gathered successfully${NC}"
echo ""

# Print values for verification
echo -e "${YELLOW}Values to be replaced:${NC}"
echo "  CLUSTER_NAME=$CLUSTER_NAME"
echo "  VPC_ID=$VPC_ID"
echo "  PUBLIC_SUBNETS=$PUBLIC_SUBNETS"
echo "  ALB_SG_ID=$ALB_SG_ID"
echo "  ALB_ROLE_ARN=$ALB_ROLE_ARN"
echo "  EXTERNAL_DNS_ROLE_ARN=$EXTERNAL_DNS_ROLE_ARN"
echo "  ESO_ROLE_ARN=$ESO_ROLE_ARN"
echo "  CLUSTER_AUTOSCALER_ROLE_ARN=$CLUSTER_AUTOSCALER_ROLE_ARN"
echo "  CERT_ARN=$CERT_ARN"
echo ""

# Navigate back to root
cd ../../../../

# Confirm before proceeding
read -p "Proceed with replacement? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo -e "${YELLOW}Aborted by user${NC}"
  exit 0
fi

echo ""
echo -e "${YELLOW}Replacing placeholders in Kubernetes manifests...${NC}"

# === AWS Load Balancer Controller ===
echo "  - infra/k8s/apps/aws-lb-controller.yaml"
sed -i.bak "s|REPLACE_WITH_CLUSTER_NAME|$CLUSTER_NAME|g" infra/k8s/apps/aws-lb-controller.yaml
sed -i.bak "s|REPLACE_WITH_ALB_ROLE_ARN|$ALB_ROLE_ARN|g" infra/k8s/apps/aws-lb-controller.yaml
sed -i.bak "s|REPLACE_WITH_VPC_ID|$VPC_ID|g" infra/k8s/apps/aws-lb-controller.yaml

# === External DNS ===
echo "  - infra/k8s/apps/external-dns.yaml"
sed -i.bak "s|REPLACE_WITH_EXTERNAL_DNS_ROLE_ARN|$EXTERNAL_DNS_ROLE_ARN|g" infra/k8s/apps/external-dns.yaml

# === External Secrets Operator ===
echo "  - infra/k8s/apps/external-secrets/helm-release.yaml"
sed -i.bak "s|REPLACE_WITH_ESO_ROLE_ARN|$ESO_ROLE_ARN|g" infra/k8s/apps/external-secrets/helm-release.yaml

# === Cluster Autoscaler ===
echo "  - infra/k8s/apps/cluster-autoscaler/cluster-autoscaler.yaml"
sed -i.bak "s|REPLACE_WITH_CLUSTER_AUTOSCALER_ROLE_ARN|$CLUSTER_AUTOSCALER_ROLE_ARN|g" infra/k8s/apps/cluster-autoscaler/cluster-autoscaler.yaml
sed -i.bak "s|REPLACE_WITH_CLUSTER_NAME|$CLUSTER_NAME|g" infra/k8s/apps/cluster-autoscaler/cluster-autoscaler.yaml

# === Client Gateway Ingress ===
echo "  - client-gateway/charts/client-gateway/templates/ingress.yaml"
sed -i.bak "s|REPLACE_WITH_ACM_CERT_ARN|$CERT_ARN|g" client-gateway/charts/client-gateway/templates/ingress.yaml
sed -i.bak "s|REPLACE_WITH_PUBLIC_SUBNET_IDS|$PUBLIC_SUBNETS|g" client-gateway/charts/client-gateway/templates/ingress.yaml
sed -i.bak "s|REPLACE_WITH_ALB_SG_ID|$ALB_SG_ID|g" client-gateway/charts/client-gateway/templates/ingress.yaml

# === Web Client Ingress ===
echo "  - web-client/charts/web-client/templates/ingress.yaml"
sed -i.bak "s|REPLACE_WITH_ACM_CERT_ARN|$CERT_ARN|g" web-client/charts/web-client/templates/ingress.yaml
sed -i.bak "s|REPLACE_WITH_PUBLIC_SUBNET_IDS|$PUBLIC_SUBNETS|g" web-client/charts/web-client/templates/ingress.yaml
sed -i.bak "s|REPLACE_WITH_ALB_SG_ID|$ALB_SG_ID|g" web-client/charts/web-client/templates/ingress.yaml

echo ""
echo -e "${GREEN}✓ All placeholders replaced successfully${NC}"
echo ""

# Clean up backup files
echo -e "${YELLOW}Cleaning up backup files...${NC}"
find infra/k8s/apps -name "*.yaml.bak" -delete
find client-gateway/charts -name "*.yaml.bak" -delete
find web-client/charts -name "*.yaml.bak" -delete

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Next Steps:${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "1. Review the changes:"
echo "   git diff infra/k8s/apps/ client-gateway/charts/ web-client/charts/"
echo ""
echo "2. Enable auto-sync in ArgoCD Applications:"
echo "   - infra/k8s/apps/aws-lb-controller.yaml"
echo "   - infra/k8s/apps/external-dns.yaml"
echo "   - infra/k8s/apps/external-secrets/helm-release.yaml"
echo "   - infra/k8s/apps/cluster-autoscaler-app.yaml"
echo "   - infra/k8s/apps/client-gateway-app.yaml"
echo "   - infra/k8s/apps/web-client-app.yaml"
echo ""
echo "   Uncomment the 'automated:' sections in syncPolicy"
echo ""
echo "3. Commit and push:"
echo "   git add ."
echo "   git commit -m 'infra: populate K8s placeholders with Terraform outputs'"
echo "   git push"
echo ""
echo "4. ArgoCD will automatically sync the applications"
echo ""
