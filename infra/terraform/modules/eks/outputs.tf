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

output "eks_admin_access_role_arn" {
  description = "ARN of the dedicated IAM role for human EKS cluster-admin access"
  value       = module.eks_admin_access_role.iam_role_arn
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

output "kubeconfig_command_admin_role" {
  description = "AWS CLI command to configure kubectl access using the dedicated EKS admin access role"
  value       = "aws eks update-kubeconfig --region ${data.aws_region.current.id} --name ${aws_eks_cluster.this.name} --role-arn ${module.eks_admin_access_role.iam_role_arn}"
}

# --- Cluster Autoscaler ---

output "cluster_autoscaler_role_arn" {
  description = "ARN of the IRSA role for the Cluster Autoscaler ServiceAccount"
  value       = module.cluster_autoscaler_role.iam_role_arn
}

# --- Instance Profile (for Karpenter EC2NodeClass) ---
output "node_instance_profile_name" {
  description = "Name of the IAM instance profile for EKS worker nodes (used by Karpenter EC2NodeClass)"
  value       = aws_iam_instance_profile.node.name
}
