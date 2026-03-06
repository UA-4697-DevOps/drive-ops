# ============================================================================
# External Secrets Operator - IRSA Role
# Allows ESO to read secrets from AWS Secrets Manager
# ============================================================================

# IAM Role for ESO ServiceAccount (IRSA)
resource "aws_iam_role" "eso_role" {
  name = "Training-${var.project_name}-${var.env}-${var.service_name}-eso-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${var.oidc_provider}:sub" = "system:serviceaccount:${var.namespace}:${var.service_name}-eso-sa"
            "${var.oidc_provider}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = var.tags
}

# IAM Policy - allow reading secrets from Secrets Manager
resource "aws_iam_policy" "eso_policy" {
  name        = "Training-${var.project_name}-${var.env}-${var.service_name}-eso-policy"
  description = "Allow ESO to read secrets for ${var.service_name}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = var.secret_arns
      }
    ]
  })

  tags = var.tags
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "eso_policy_attachment" {
  role       = aws_iam_role.eso_role.name
  policy_arn = aws_iam_policy.eso_policy.arn
}

# Secret for Driver Service - DATABASE_URL
resource "aws_secretsmanager_secret" "driver_service_secret" {
  name        = "${var.project_name}/${var.env}/${var.service_name}/config"
  description = "Configuration secrets for ${var.service_name} in ${var.env}"
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "driver_service_secret" {
  secret_id = aws_secretsmanager_secret.driver_service_secret.id
  secret_string = jsonencode({
    database_url = var.database_url
  })
}
