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

output "ssm_trip_service_prefix" {
  description = "SSM Parameter Store path prefix for TripService config"
  value       = "/${var.project_name}/${var.env}/trip-service"
}
