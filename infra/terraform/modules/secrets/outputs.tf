output "rds_master_secret_arn" {
  description = "ARN of the Secrets Manager secret containing RDS master credentials (username and password). Retrieve the actual credentials at runtime from Secrets Manager."
  value       = aws_secretsmanager_secret.rds_credentials.arn
}

output "rds_master_secret_name" {
  description = "Name of the Secrets Manager secret containing RDS master credentials. Use this to retrieve credentials via AWS CLI or SDK."
  value       = aws_secretsmanager_secret.rds_credentials.name
}

output "rds_master_secret_id" {
  description = "ID of the Secrets Manager secret. Use this for referencing the secret in other Terraform resources."
  value       = aws_secretsmanager_secret.rds_credentials.id
}

output "discord_webhook_secret_arn" {
  description = "ARN of the Secrets Manager secret for Discord webhook"
  value       = aws_secretsmanager_secret.discord_webhook.arn
}
