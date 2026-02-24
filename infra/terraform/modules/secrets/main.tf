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
  name        = "${var.project_name}/${var.env}/rds/credentials-v2"
  description = "RDS master credentials for ${var.project_name} ${var.env}"
  tags        = var.tags
  lifecycle {
    create_before_destroy = true
  }
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
  name        = "${var.project_name}/${var.env}/monitoring/discord-v2"
  description = "Discord Webhook URL for alerting"
  tags        = var.tags
  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_secretsmanager_secret_version" "discord_webhook_val" {
  secret_id = aws_secretsmanager_secret.discord_webhook.id
  secret_string = jsonencode({
    url = var.discord_webhook_url
  })
}
