resource "random_password" "master_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"

  keepers = {
    db_identifier = var.db_identifier
  }
}

resource "aws_secretsmanager_secret" "rds_credentials" {
  name = "${var.project_name}/${var.env}/rds/credentials"
  description = "RDS master credentials for ${var.project_name} ${var.env}"

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "rds_credentials" {
  secret_id = aws_secretsmanager_secret.rds_credentials.id
  secret_string = jsonencode({
      username = var.rds_master_username
      password = random_password.master_password.result
      engine   = "postgres"
    })
}