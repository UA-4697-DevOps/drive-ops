#!/bin/bash
# ==============================================================================
# MANUAL PLACEHOLDER REPLACEMENT
# ==============================================================================
# Paste the values you copied from bastion below, then run this script
# ==============================================================================

# ========== PASTE YOUR VALUES HERE ==========
CLUSTER_NAME="PASTE_VALUE_HERE"
VPC_ID="PASTE_VALUE_HERE"
PUBLIC_SUBNETS="PASTE_VALUE_HERE"  # comma-separated
ALB_SG_ID="PASTE_VALUE_HERE"
ALB_ROLE_ARN="PASTE_VALUE_HERE"
EXTERNAL_DNS_ROLE_ARN="PASTE_VALUE_HERE"
ESO_ROLE_ARN="PASTE_VALUE_HERE"
CLUSTER_AUTOSCALER_ROLE_ARN="PASTE_VALUE_HERE"
CERT_ARN="PASTE_VALUE_HERE"
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
