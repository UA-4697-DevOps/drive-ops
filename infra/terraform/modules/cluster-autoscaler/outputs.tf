output "cluster_autoscaler_role_arn" {
  description = "ARN of the IAM role for Cluster Autoscaler IRSA"
  value       = aws_iam_role.cluster_autoscaler.arn
}

output "cluster_autoscaler_role_name" {
  description = "Name of the IAM role for Cluster Autoscaler"
  value       = aws_iam_role.cluster_autoscaler.name
}
