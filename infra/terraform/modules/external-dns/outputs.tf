# ==============================================================================
# EXTERNAL DNS – OUTPUTS
# ==============================================================================

output "external_dns_role_arn" {
  description = "ARN of the IAM role for External DNS"
  value       = aws_iam_role.external_dns.arn
}

output "external_dns_role_name" {
  description = "Name of the IAM role for External DNS"
  value       = aws_iam_role.external_dns.name
}

output "external_dns_policy_arn" {
  description = "ARN of the IAM policy for External DNS"
  value       = aws_iam_policy.external_dns.arn
}
