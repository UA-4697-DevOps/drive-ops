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
  ecr_url_parts      = var.ecr_repository_url != null ? split("/", replace(var.ecr_repository_url, "https://", "")) : []
  ecr_registry_parts = length(local.ecr_url_parts) > 0 ? split(".", local.ecr_url_parts[0]) : []
  ecr_repo_name      = length(local.ecr_url_parts) > 1 ? split(":", local.ecr_url_parts[1])[0] : null

  derived_ecr_repository_arn = (
    length(local.ecr_registry_parts) >= 4 &&
    local.ecr_repo_name != null
    ) ? format(
    "arn:aws:ecr:%s:%s:repository/%s",
    local.ecr_registry_parts[3],
    local.ecr_registry_parts[0],
    local.ecr_repo_name
  ) : null

  resolved_ecr_repository_arn = coalesce(var.ecr_repository_arn, local.derived_ecr_repository_arn)

  ec2_custom_policies = {
    # ECR Pull Access
    ecr_pull = local.resolved_ecr_repository_arn != null ? {
      policy_name = "${var.name}-ecr-pull"
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
            Resource = local.resolved_ecr_repository_arn
          }
        ]
      })
    } : null

    # SSM Parameter Store Access
    ssm_read = {
      policy_name = "${var.name}-ssm-read"
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
    }

    # Secrets Manager Access
    secrets_read = length(var.iam_secret_arns) > 0 ? {
      policy_name = "${var.name}-secrets-read"
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
    } : null

    # SQS Access
    sqs_access = length(var.iam_sqs_arns) > 0 ? {
      policy_name = "${var.name}-sqs-access"
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
    } : null

    # RDS Discovery Access
    rds_discovery = {
      policy_name = "${var.name}-rds-discovery"
      policy = jsonencode({
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

# Note: custom policy keys are now stable logical keys (e.g., ecr_pull, ssm_read),
# so future moved blocks can target static addresses safely when needed.
