output "eso_role_arn" {
  description = "ARN of the IAM role for External Secrets Operator"
  value       = aws_iam_role.eso.arn
}

output "eso_role_name" {
  description = "Name of the IAM role for External Secrets Operator"
  value       = aws_iam_role.eso.name
}

output "eso_policy_arn" {
  description = "ARN of the IAM policy for External Secrets Operator"
  value       = aws_iam_policy.eso_secrets_policy.arn
}
