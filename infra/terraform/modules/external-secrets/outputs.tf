output "eso_role_arn" {
  description = "ARN of the IRSA role for External Secrets Operator"
  value       = aws_iam_role.eso.arn
}

output "eso_role_name" {
  description = "Name of the IRSA role for External Secrets Operator"
  value       = aws_iam_role.eso.name
}
