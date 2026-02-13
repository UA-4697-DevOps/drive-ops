variable "sns_topic_arn" {
  description = "The ARN of the SNS topic that triggers this Lambda"
  type        = string
}

variable "discord_webhook_url" {
  description = "The Discord Webhook URL for sending notifications"
  type        = string
  sensitive   = true # Marks this as sensitive in CLI output
}
