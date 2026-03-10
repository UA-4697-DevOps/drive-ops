#!/bin/bash
# ==============================================================================
# MANUAL PLACEHOLDER REPLACEMENT
# ==============================================================================
# Paste the values you copied from bastion below, then run this script
# ==============================================================================

# ========== PASTE YOUR VALUES HERE ==========
CLUSTER_NAME="Training-drive-ops-dev-eks"
VPC_ID="vpc-00f7c0f744f4032d4"
PUBLIC_SUBNETS="subnet-0a0dcdc19a2f78e4d,subnet-0658bcf6b0175cad2"
ALB_SG_ID="sg-0d93c034f6a242aa0"
ALB_ROLE_ARN="arn:aws:iam::969283154407:role/Training-drive-ops-dev-alb-controller-role"
EXTERNAL_DNS_ROLE_ARN="arn:aws:iam::969283154407:role/Training-drive-ops-dev-external-dns-role"
ESO_ROLE_ARN="arn:aws:iam::969283154407:role/Training-drive-ops-dev-eso-role"
CLUSTER_AUTOSCALER_ROLE_ARN="arn:aws:iam::969283154407:role/Training-drive-ops-dev-cluster-autoscaler-role"
CERT_ARN="arn:aws:acm:us-east-2:969283154407:certificate/48dd9e5e-6e92-4caa-88ab-95636766268c"
# ============================================

set -euo pipefail

echo "========================================"
echo "Manual Placeholder Replacement"
echo "========================================"
echo ""

# Validate values
if [[ "$CLUSTER_NAME" == "PASTE_VALUE_HERE" ]]; then
  echo "ERROR: Please edit this script and paste your values first!"
  exit 1
fi

echo "Values to be replaced:"
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

read -p "Proceed with replacement? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted"
  exit 0
fi

echo ""
echo "Replacing placeholders..."

# AWS Load Balancer Controller
echo "  - infra/k8s/apps/aws-lb-controller.yaml"
sed -i.bak "s|REPLACE_WITH_CLUSTER_NAME|$CLUSTER_NAME|g" infra/k8s/apps/aws-lb-controller.yaml
sed -i.bak "s|REPLACE_WITH_ALB_ROLE_ARN|$ALB_ROLE_ARN|g" infra/k8s/apps/aws-lb-controller.yaml
sed -i.bak "s|REPLACE_WITH_VPC_ID|$VPC_ID|g" infra/k8s/apps/aws-lb-controller.yaml

# External DNS
echo "  - infra/k8s/apps/external-dns.yaml"
sed -i.bak "s|REPLACE_WITH_EXTERNAL_DNS_ROLE_ARN|$EXTERNAL_DNS_ROLE_ARN|g" infra/k8s/apps/external-dns.yaml

# External Secrets Operator
echo "  - infra/k8s/apps/external-secrets/helm-release.yaml"
sed -i.bak "s|REPLACE_WITH_ESO_ROLE_ARN|$ESO_ROLE_ARN|g" infra/k8s/apps/external-secrets/helm-release.yaml

# Cluster Autoscaler
echo "  - infra/k8s/apps/cluster-autoscaler/cluster-autoscaler.yaml"
sed -i.bak "s|REPLACE_WITH_CLUSTER_AUTOSCALER_ROLE_ARN|$CLUSTER_AUTOSCALER_ROLE_ARN|g" infra/k8s/apps/cluster-autoscaler/cluster-autoscaler.yaml
sed -i.bak "s|REPLACE_WITH_CLUSTER_NAME|$CLUSTER_NAME|g" infra/k8s/apps/cluster-autoscaler/cluster-autoscaler.yaml

# Client Gateway Ingress
echo "  - client-gateway/charts/client-gateway/templates/ingress.yaml"
sed -i.bak "s|REPLACE_WITH_ACM_CERT_ARN|$CERT_ARN|g" client-gateway/charts/client-gateway/templates/ingress.yaml
sed -i.bak "s|REPLACE_WITH_PUBLIC_SUBNET_IDS|$PUBLIC_SUBNETS|g" client-gateway/charts/client-gateway/templates/ingress.yaml
sed -i.bak "s|REPLACE_WITH_ALB_SG_ID|$ALB_SG_ID|g" client-gateway/charts/client-gateway/templates/ingress.yaml

# Web Client Ingress
echo "  - web-client/charts/web-client/templates/ingress.yaml"
sed -i.bak "s|REPLACE_WITH_ACM_CERT_ARN|$CERT_ARN|g" web-client/charts/web-client/templates/ingress.yaml
sed -i.bak "s|REPLACE_WITH_PUBLIC_SUBNET_IDS|$PUBLIC_SUBNETS|g" web-client/charts/web-client/templates/ingress.yaml
sed -i.bak "s|REPLACE_WITH_ALB_SG_ID|$ALB_SG_ID|g" web-client/charts/web-client/templates/ingress.yaml

echo ""
echo "✓ All placeholders replaced successfully"
echo ""

# Clean up backup files
echo "Cleaning up backup files..."
find infra/k8s/apps -name "*.yaml.bak" -delete
find client-gateway/charts -name "*.yaml.bak" -delete
find web-client/charts -name "*.yaml.bak" -delete

echo ""
echo "========================================"
echo "Done! Review changes with:"
echo "  git diff"
echo ""
echo "Next: Uncomment auto-sync in ArgoCD apps"
echo "========================================"
