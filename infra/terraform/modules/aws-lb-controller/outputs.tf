# ==============================================================================
# AWS LOAD BALANCER CONTROLLER – OUTPUTS
# ==============================================================================

output "alb_controller_role_arn" {
  description = "ARN of the IAM role for AWS Load Balancer Controller"
  value       = module.iam_role.iam_role_arn
}

output "alb_controller_role_name" {
  description = "Name of the IAM role for AWS Load Balancer Controller"
  value       = module.iam_role.iam_role_name
}

output "alb_controller_policy_arn" {
  description = "ARN of the IAM policy for AWS Load Balancer Controller"
  value       = local.alb_controller_policy_arn
}
