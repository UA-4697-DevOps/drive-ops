# ==============================================================================
# EXTERNAL DNS – OUTPUTS
# ==============================================================================

output "external_dns_role_arn" {
  description = "ARN of the IAM role for External DNS"
  value       = module.external_dns_iam_role.iam_role_arn
}

output "external_dns_role_name" {
  description = "Name of the IAM role for External DNS"
  value       = module.external_dns_iam_role.iam_role_name
}
