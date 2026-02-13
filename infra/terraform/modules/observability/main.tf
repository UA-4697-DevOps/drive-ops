# 1. Fetch the actual Webhook URL from Secrets Manager using the provided ARN
data "aws_secretsmanager_secret_version" "discord_webhook" {
  secret_id = var.discord_webhook_secret_arn
}

# 2. Setup the SNS Notification Topic for all drive-ops alerts
module "sns" {
  source = "../sns"
}

# 3. Setup CloudWatch Logs and Alarms for services and database
module "cloudwatch" {
  source          = "../cloudwatch"
  service_names   = var.service_names
  rds_instance_id = var.rds_instance_id
  sns_topic_arn   = module.sns.sns_topic_arn
}

# 4. Setup Lambda for Discord Notifications
module "lambda_discord" {
  source              = "../lambda-discord"
  sns_topic_arn       = module.sns.sns_topic_arn
  # Pass the secret string retrieved from AWS Secrets Manager
  discord_webhook_url = data.aws_secretsmanager_secret_version.discord_webhook.secret_string
}
