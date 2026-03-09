# --- 1. RDS Master Password ---
resource "random_password" "master_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"

  keepers = {
    db_identifier = var.db_identifier
  }
}

resource "aws_secretsmanager_secret" "rds_credentials" {
  name        = "${var.project_name}/${var.env}/rds/credentials"
  description = "RDS master credentials for ${var.project_name} ${var.env}"
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "rds_credentials" {
  secret_id = aws_secretsmanager_secret.rds_credentials.id
  secret_string = jsonencode({
    username = var.rds_master_username
    password = random_password.master_password.result
    engine   = "postgres"
  })
}

# --- 2. Discord Webhook (NEW) ---
resource "aws_secretsmanager_secret" "discord_webhook" {
  name        = "${var.project_name}/${var.env}/monitoring/discord"
  description = "Discord Webhook URL for alerting"
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "discord_webhook_val" {
  secret_id = aws_secretsmanager_secret.discord_webhook.id
  secret_string = jsonencode({
    url = var.discord_webhook_url
  })
}

# --- 3. Telegram Bot Token ---
resource "aws_secretsmanager_secret" "telegram_bot_token" {
  name        = "${var.project_name}/${var.env}/client-gateway/bot"
  description = "Telegram Bot Token for client-gateway"
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "telegram_bot_token_val" {
  secret_id = aws_secretsmanager_secret.telegram_bot_token.id
  secret_string = jsonencode({
    token = var.telegram_bot_token
  })
}
