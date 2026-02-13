variable "service_names" {
  description = "List of services to create CloudWatch Log Groups for (e.g., trip-service, driver-service)"
  type        = set(string)
}

variable "rds_instance_id" {
  description = "The ID of the RDS instance for monitoring CPU and Storage"
  type        = string
}

variable "discord_webhook_secret_arn" {
  description = "The ARN of the secret in Secrets Manager containing the Discord Webhook URL"
  type        = string
}

variable "environment" {
  description = "Deployment environment (e.g., dev, prod)"
  type        = string
  default     = "dev"
}
