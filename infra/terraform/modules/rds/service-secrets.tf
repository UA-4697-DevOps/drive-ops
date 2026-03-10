# ==============================================================================
# SERVICE-SPECIFIC SECRETS
# ==============================================================================
# This file manages AWS Secrets Manager secrets for each service that needs
# RDS connection information. External Secrets Operator will sync these to K8s.
#
# NOTE: The secrets themselves are assumed to already exist (created manually
# or by another process). This module only manages the secret versions/values.
# ==============================================================================

# --- Driver Service Secret ---
data "aws_secretsmanager_secret" "driver_service" {
  name = "${var.project_name}/${var.env}/driver-service"
}

resource "aws_secretsmanager_secret_version" "driver_service" {
  secret_id = data.aws_secretsmanager_secret.driver_service.id
  secret_string = jsonencode({
    RDS_ENDPOINT = aws_db_instance.main.endpoint
    DB_NAME      = "driver_db"
  })
}

# --- Trip Service Secret ---
data "aws_secretsmanager_secret" "trip_service" {
  name = "${var.project_name}/${var.env}/trip-service"
}

resource "aws_secretsmanager_secret_version" "trip_service" {
  secret_id = data.aws_secretsmanager_secret.trip_service.id
  secret_string = jsonencode({
    RDS_ENDPOINT = aws_db_instance.main.endpoint
    DB_USER      = aws_db_instance.main.username
  })
}
