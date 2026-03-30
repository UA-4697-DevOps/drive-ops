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

# --- EC2 IAM Role (managed by iam-role module) ---

# Build custom policies map with conditional logic
locals {
  ec2_custom_policies = {
    # ECR Pull Access
    "${var.name}-ecr-pull" = var.ecr_repository_url != null ? jsonencode({
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
    }) : null

    # SSM Parameter Store Access
    "${var.name}-ssm-read" = jsonencode({
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

    # Secrets Manager Access
    "${var.name}-secrets-read" = length(var.iam_secret_arns) > 0 ? jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect   = "Allow"
          Action   = ["secretsmanager:GetSecretValue"]
          Resource = var.iam_secret_arns
        }
      ]
    }) : null

    # SQS Access
    "${var.name}-sqs-access" = length(var.iam_sqs_arns) > 0 ? jsonencode({
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
    }) : null

    # RDS Discovery Access
    "${var.name}-rds-discovery" = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect   = "Allow"
          Action   = ["rds:DescribeDBInstances"]
          Resource = "*"
        }
      ]
    })
  }

  # Filter out null policies before passing to module
  filtered_custom_policies = {
    for k, v in local.ec2_custom_policies : k => v if v != null
  }
}

module "ec2_iam_role" {
  source = "../iam-role"

  role_name               = "${var.name}-ec2-role"
  assume_role_policy      = data.aws_iam_policy_document.ec2_assume_role.json
  permissions_boundary    = local.permissions_boundary
  create_instance_profile = true

  managed_policy_arns = [
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  ]

  custom_policies = local.filtered_custom_policies

  tags = var.tags
}

# --- State Migrations (preserve existing resources) ---

moved {
  from = aws_iam_role.ec2_ssm_role
  to   = module.ec2_iam_role.aws_iam_role.this
}

moved {
  from = aws_iam_instance_profile.ec2_profile
  to   = module.ec2_iam_role.aws_iam_instance_profile.this[0]
}

moved {
  from = aws_iam_role_policy_attachment.ssm_managed_instance
  to   = module.ec2_iam_role.aws_iam_role_policy_attachment.managed_attach["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"]
}

# Note: moved blocks for custom policies cannot be used due to dynamic keys (${var.name} interpolation).
# Terraform moved blocks only support static references. The custom policies will be created fresh
# if they don't already exist in the iam-role module state. This is safe because:
# 1. Custom policies are derived from var.ecr_repository_url and var.iam_* variables
# 2. If those variables don't change, policies will be identical
# 3. The role and attachments are preserved via moved blocks above
