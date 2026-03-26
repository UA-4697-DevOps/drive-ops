# Create the ECR Repository for the service
resource "aws_ecr_repository" "service_repository" {
  name                 = var.repository_name
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# --- GitHub Actions CI Role (Main Branch Only) ---

data "aws_iam_policy_document" "ci_assume_role" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"
    principals {
      type        = "Federated"
      identifiers = ["arn:aws:iam::${var.account_id}:oidc-provider/token.actions.githubusercontent.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/main"]
    }
  }
}

module "ci_role" {
  source = "../iam-role"

  role_name            = "Training-${var.repository_name}-github-actions-role"
  assume_role_policy   = data.aws_iam_policy_document.ci_assume_role.json
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  custom_policies = {
    "Training-${var.repository_name}-ecr-push-policy" = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Action   = "ecr:GetAuthorizationToken"
          Effect   = "Allow"
          Resource = "*"
        },
        {
          Action = [
            "ecr:BatchCheckLayerAvailability",
            "ecr:GetDownloadUrlForLayer",
            "ecr:BatchGetImage",
            "ecr:PutImage",
            "ecr:InitiateLayerUpload",
            "ecr:UploadLayerPart",
            "ecr:CompleteLayerUpload"
          ]
          Effect   = "Allow"
          Resource = aws_ecr_repository.service_repository.arn
        }
      ]
    })

    "Training-${var.repository_name}-terraform-backend-policy" = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Sid    = "S3BackendAccess"
          Effect = "Allow"
          Action = [
            "s3:ListBucket",
            "s3:GetBucketLocation",
            "s3:HeadBucket",
            "s3:GetObject",
            "s3:PutObject"
          ]
          Resource = [
            "arn:aws:s3:::drive-ops-dev-terraform-state",
            "arn:aws:s3:::drive-ops-dev-terraform-state/*"
          ]
        },
        {
          Sid    = "DynamoDBLockAccess"
          Effect = "Allow"
          Action = [
            "dynamodb:DescribeTable",
            "dynamodb:GetItem",
            "dynamodb:PutItem",
            "dynamodb:DeleteItem"
          ]
          Resource = "arn:aws:dynamodb:*:*:table/drive-ops-dev-terraform-locks"
        }
      ]
    })
  }

  tags = var.tags
}

# --- GitHub Actions Deploy Role (workflow_dispatch) ---

data "aws_iam_policy_document" "deploy_assume_role" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"
    principals {
      type        = "Federated"
      identifiers = ["arn:aws:iam::${var.account_id}:oidc-provider/token.actions.githubusercontent.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:environment:dev"]
    }
  }
}

module "deploy_role" {
  source = "../iam-role"

  role_name            = "Training-${var.repository_name}-deploy-role"
  assume_role_policy   = data.aws_iam_policy_document.deploy_assume_role.json
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  custom_policies = {
    "Training-${var.repository_name}-ecr-push-policy" = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Action   = "ecr:GetAuthorizationToken"
          Effect   = "Allow"
          Resource = "*"
        },
        {
          Action = [
            "ecr:BatchCheckLayerAvailability",
            "ecr:GetDownloadUrlForLayer",
            "ecr:BatchGetImage",
            "ecr:PutImage",
            "ecr:InitiateLayerUpload",
            "ecr:UploadLayerPart",
            "ecr:CompleteLayerUpload"
          ]
          Effect   = "Allow"
          Resource = aws_ecr_repository.service_repository.arn
        }
      ]
    })
  }

  tags = var.tags
}

# ECR Lifecycle Policy to manage storage costs
resource "aws_ecr_lifecycle_policy" "cleanup_policy" {
  repository = aws_ecr_repository.service_repository.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1,
      description  = "Keep only the last 5 images",
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 },
      action       = { type = "expire" }
    }]
  })
}

# --- State Migrations (preserve existing resources) ---

moved {
  from = aws_iam_role.role
  to   = module.ci_role.aws_iam_role.this
}

moved {
  from = aws_iam_role.deploy_role
  to   = module.deploy_role.aws_iam_role.this
}
