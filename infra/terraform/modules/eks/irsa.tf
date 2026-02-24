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

# Fetch the OIDC issuer certificate to extract the thumbprint for AWS provider 5.0+
data "tls_certificate" "eks_oidc" {
  url = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

# ------------------------------------------------------------------------------
# OIDC IDENTITY PROVIDER
# ------------------------------------------------------------------------------

resource "aws_iam_openid_connect_provider" "eks" {
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks_oidc.certificates[0].sha1_fingerprint]

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-oidc"
  })
}
