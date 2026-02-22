# ==============================================================================
# EKS MODULE – OUTPUTS
# ==============================================================================

# --- Cluster ---

output "cluster_name" {
  description = "Name of the EKS cluster"
  value       = aws_eks_cluster.this.name
}

output "cluster_arn" {
  description = "ARN of the EKS cluster"
  value       = aws_eks_cluster.this.arn
}

output "cluster_endpoint" {
  description = "Endpoint URL for the EKS API server"
  value       = aws_eks_cluster.this.endpoint
}

output "cluster_certificate_authority_data" {
  description = "Base64-encoded certificate authority data for the cluster"
  value       = aws_eks_cluster.this.certificate_authority[0].data
}

output "cluster_version" {
  description = "Kubernetes version running on the cluster"
  value       = aws_eks_cluster.this.version
}

output "cluster_platform_version" {
  description = "EKS platform version"
  value       = aws_eks_cluster.this.platform_version
}

# --- Networking ---

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster control plane"
  value       = aws_security_group.eks_cluster.id
}

output "node_security_group_id" {
  description = "Security group ID attached to the EKS worker nodes"
  value       = aws_security_group.eks_nodes.id
}

# --- Node Group ---

output "node_group_name" {
  description = "Name of the managed node group"
  value       = aws_eks_node_group.default.node_group_name
}

output "node_group_arn" {
  description = "ARN of the managed node group"
  value       = aws_eks_node_group.default.arn
}

output "node_group_status" {
  description = "Status of the managed node group"
  value       = aws_eks_node_group.default.status
}

# --- IAM ---

output "cluster_role_arn" {
  description = "ARN of the IAM role used by the EKS cluster"
  value       = aws_iam_role.eks_cluster.arn
}

output "node_role_arn" {
  description = "ARN of the IAM role used by the EKS worker nodes"
  value       = aws_iam_role.node_group.arn
}

# --- OIDC / IRSA ---

output "oidc_provider_arn" {
  description = "ARN of the OIDC identity provider (used for IRSA trust policies)"
  value       = aws_iam_openid_connect_provider.eks.arn
}

output "oidc_provider_url" {
  description = "OIDC issuer URL without the https:// prefix (used in trust policy conditions)"
  value       = replace(aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")
}

# --- Kubeconfig ---

output "kubeconfig_command" {
  description = "AWS CLI command to configure kubectl access to the cluster"
  value       = "aws eks update-kubeconfig --region ${data.aws_region.current.id} --name ${aws_eks_cluster.this.name}"
}
