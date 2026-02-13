# Create the ECR Repository for the service
resource "aws_ecr_repository" "service_repository" {
  name                 = var.repository_name
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# --- IAM Role for GitHub Actions (Strict Main Branch Only) ---
resource "aws_iam_role" "github_actions" {
  name = "${var.repository_name}-github-actions-role"

  # Satisfies environment constraints for restricted IAM creation
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = "arn:aws:iam::${var.account_id}:oidc-provider/token.actions.githubusercontent.com"
        }
        Condition = {
          # MENTOR'S RULE: Only the main branch is authorized to assume this role
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:ref:refs/heads/main"
          }
        }
      }
    ]
  })
}

# 1. ECR Push Policy (Least Privilege for Docker images)
resource "aws_iam_policy" "ecr_push_policy" {
  name        = "${var.repository_name}-ecr-push-policy"
  description = "Minimal permissions to push images to ${var.repository_name}"

  policy = jsonencode({
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

# --- 2. Terraform Backend Access Policy ---
# Required permissions for successful pipeline execution in the main branch.
# This allows Terraform to check the state file and locking table.
resource "aws_iam_policy" "terraform_backend_policy" {
  name        = "${var.repository_name}-terraform-backend-policy"
  description = "Permissions for GitHub Actions to manage Terraform State"

  policy = jsonencode({
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
        Resource = "arn:aws:dynamodb:*:*:table/drive-ops-dev-terraform-state-lock"
      }
    ]
  })
}

# Attach both policies to the role
resource "aws_iam_role_policy_attachment" "ecr_policy" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.ecr_push_policy.arn
}

resource "aws_iam_role_policy_attachment" "backend_policy" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.terraform_backend_policy.arn
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
