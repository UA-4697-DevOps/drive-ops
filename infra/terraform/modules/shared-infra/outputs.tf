
    web_client     = module.ecr_web_client.role_arn
  }
}

output "ecr_iam_role_names" {
  description = "IAM Role names for GitHub Actions (for policy attachment)"
  value = {
    client_gateway = module.ecr_client_gateway.role_name
    driver_service = module.ecr_driver_service.role_name
    trip_service   = module.ecr_trip_service.role_name
    web_client     = module.ecr_web_client.role_name
  }
}

# --- Encryption (KMS) ---
output "kms_key_arn" {
  description = "ARN of the customer-managed KMS key"
  value       = aws_kms_key.cmk.arn
}

output "kms_key_id" {
  description = "ID of the customer-managed KMS key"
  value       = aws_kms_key.cmk.key_id
}

# --- Secrets ---
output "rds_secret_arn" {
  description = "ARN of the Secrets Manager secret for RDS credentials"
  value       = module.rds_secrets.rds_master_secret_arn
}

output "rds_secret_name" {
  description = "Friendly name of the RDS secret"
  value       = module.rds_secrets.rds_master_secret_name
}

output "discord_secret_arn" {
  description = "ARN of the Secrets Manager secret containing the Discord Webhook URL"
  value       = module.rds_secrets.discord_secret_arn
}

output "telegram_bot_secret_arn" {
  description = "ARN of the Secrets Manager secret containing the Telegram Bot Token"
  value       = module.rds_secrets.telegram_bot_secret_arn
}
