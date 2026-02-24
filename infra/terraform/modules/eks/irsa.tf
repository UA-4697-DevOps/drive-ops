# ==============================================================================
# EKS MODULE – OIDC PROVIDER & IRSA
# ==============================================================================
# Creates:
#   1. OIDC identity provider for the EKS cluster
#   2. A reusable pattern for IAM Roles for Service Accounts (IRSA)
#
# The OIDC provider allows Kubernetes service accounts to assume IAM roles
# without embedding long-lived credentials in pods.
# ==============================================================================

# IAM auto-manages the OIDC thumbprint, so no explicit TLS certificate fetch is needed.

# ------------------------------------------------------------------------------
# OIDC IDENTITY PROVIDER
# ------------------------------------------------------------------------------

resource "aws_iam_openid_connect_provider" "eks" {
  url            = aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list = ["sts.amazonaws.com"]

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-oidc"
  })
}
