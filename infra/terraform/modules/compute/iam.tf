# ============================================================================
# IAM Configuration for EC2 Instance
# ============================================================================

# This data source was missing from data.tf, so we declare it here.
data "aws_caller_identity" "current" {}

# Note: data.aws_region.current and local.permissions_boundary are 
# already declared in data.tf. We do not re-declare them to avoid duplicates.

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

# --- EC2 IAM Role ---

resource "aws_iam_role" "ec2_ssm_role" {
  # var.name includes the "Training-" prefix from Terragrunt to pass the boundary
  name                 = "${var.name}-ec2-role"
  assume_role_policy   = data.aws_iam_policy_document.ec2_assume_role.json
  permissions_boundary = local.permissions_boundary
  tags                 = var.tags
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.name}-profile"
  role = aws_iam_role.ec2_ssm_role.name
  tags = var.tags
}

# Standard policy for Systems Manager (SSM) managed instances
resource "aws_iam_role_policy_attachment" "ssm_managed_instance" {
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# --- 1. ECR Pull Access ---

resource "aws_iam_policy" "ecr_pull" {
  count       = var.ecr_repository_url != null ? 1 : 0
  name        = "${var.name}-ecr-pull"
  description = "Allow EC2 to pull images from ECR"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      }
    ]
  })
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ecr_pull" {
  count      = var.ecr_repository_url != null ? 1 : 0
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = aws_iam_policy.ecr_pull[0].arn
}

# --- 2. SSM Parameter Store Access ---

resource "aws_iam_policy" "ssm_config_read" {
  count       = 1
  name        = "${var.name}-ssm-read"
  description = "Allow EC2 to read app config from SSM Parameter Store"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.env}/*"
      }
    ]
  })
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ssm_config_read" {
  count      = 1
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = aws_iam_policy.ssm_config_read[0].arn
}

# --- 3. Secrets Manager Access (Database) ---

resource "aws_iam_policy" "secrets_read" {
  count       = length(var.iam_secret_arns) > 0 ? 1 : 0
  name        = "${var.name}-secrets-read"
  description = "Allow EC2 to read DB credentials from Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.iam_secret_arns
      }
    ]
  })
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "secrets_read" {
  count      = length(var.iam_secret_arns) > 0 ? 1 : 0
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = aws_iam_policy.secrets_read[0].arn
}

# --- 4. SQS Access (Messaging) ---

resource "aws_iam_policy" "sqs_access" {
  count       = length(var.iam_sqs_arns) > 0 ? 1 : 0
  name        = "${var.name}-sqs-access"
  description = "Allow EC2 to access specific SQS queues"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = var.iam_sqs_arns
      }
    ]
  })
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "sqs_access" {
  count      = length(var.iam_sqs_arns) > 0 ? 1 : 0
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = aws_iam_policy.sqs_access[0].arn
}

# --- State Migrations ---

moved {
  from = aws_iam_policy.ecr_pull
  to   = aws_iam_policy.ecr_pull[0]
}

moved {
  from = aws_iam_role_policy_attachment.ecr_pull
  to   = aws_iam_role_policy_attachment.ecr_pull[0]
}

moved {
  from = aws_iam_policy.ssm_config_read
  to   = aws_iam_policy.ssm_config_read[0]
}

moved {
  from = aws_iam_role_policy_attachment.ssm_config_read
  to   = aws_iam_role_policy_attachment.ssm_config_read[0]
}
