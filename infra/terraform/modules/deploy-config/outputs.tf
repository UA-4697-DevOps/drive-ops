# =============================================================================
# Outputs for Deploy Config Module
# =============================================================================

output "deploy_policy_arn" {
  description = "ARN of the IAM policy granting deploy permissions"
  value       = aws_iam_policy.deploy_policy.arn
}

output "ssm_parameter_prefix" {
  description = "SSM Parameter Store path prefix for this environment"
  value       = "/${var.project_name}/${var.env}"
}

output "ssm_parameter_arns" {
  description = "Map of all created SSM parameter ARNs, keyed by path suffix"
  value       = { for k, v in aws_ssm_parameter.this : k => v.arn }
}
