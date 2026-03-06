output "eso_role_arn" {
  description = "ARN of the IAM role for ESO ServiceAccount (IRSA)"
  value       = aws_iam_role.eso_role.arn
}

output "eso_role_name" {
  description = "Name of the IAM role for ESO"
  value       = aws_iam_role.eso_role.name
}

output "secret_arn" {
  description = "ARN of the Secrets Manager secret for this service"
  value       = aws_secretsmanager_secret.driver_service_secret.arn
}

output "secret_name" {
  description = "Name of the Secrets Manager secret"
  value       = aws_secretsmanager_secret.driver_service_secret.name
}
