# ==============================================================================
# EKS MODULE – OUTPUTS
# ==============================================================================

# --- Cluster ---

output "cluster_name" {
  description = "Name of the EKS cluster"
  value       = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  description = "Endpoint URL for the EKS API server"
  value       = aws_eks_cluster.this.endpoint
  sensitive   = true
}

output "cluster_certificate_authority_data" {
  description = "Base64-encoded certificate authority data for the cluster"
  value       = aws_eks_cluster.this.certificate_authority[0].data
  sensitive   = true
}

# --- IAM ---

output "cluster_role_arn" {
  description = "ARN of the IAM role used by the EKS cluster"
  value       = module.eks_cluster_role.iam_role_arn
}

output "node_role_arn" {
  description = "ARN of the IAM role used by the EKS worker nodes"
  value       = module.node_group_role.iam_role_arn
}

# --- OIDC / IRSA ---

output "oidc_provider_arn" {
  description = "ARN of the OIDC identity provider (used for IRSA trust policies)"
  value       = aws_iam_openid_connect_provider.eks.arn
  sensitive   = true
}

output "oidc_provider_url" {
  description = "OIDC issuer URL without the https:// prefix (used in trust policy conditions)"
  value       = replace(aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")
  sensitive   = true
}

# --- Kubeconfig ---

output "kubeconfig_command" {
  description = "AWS CLI command to configure kubectl access to the cluster"
  value       = "aws eks update-kubeconfig --region ${data.aws_region.current.id} --name ${aws_eks_cluster.this.name}"
}

# --- Cluster Autoscaler ---

output "cluster_autoscaler_role_arn" {
  description = "ARN of the IRSA role for the Cluster Autoscaler ServiceAccount"
  value       = aws_iam_role.cluster_autoscaler.arn
}
