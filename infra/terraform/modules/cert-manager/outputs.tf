# ==============================================================================
# CERT-MANAGER – OUTPUTS
# ==============================================================================

output "cert_manager_role_arn" {
  description = "ARN of the IAM role for cert-manager"
  value       = aws_iam_role.cert_manager.arn
}

output "cert_manager_role_name" {
  description = "Name of the IAM role for cert-manager"
  value       = aws_iam_role.cert_manager.name
}

output "cert_manager_policy_arn" {
  description = "ARN of the IAM policy for cert-manager"
  value       = aws_iam_policy.cert_manager.arn
}
