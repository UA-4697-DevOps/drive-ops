# Create the ECR Repository for the service with a descriptive resource name
resource "aws_ecr_repository" "service_repository" {
  name                 = var.repository_name
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# IAM Role for GitHub Actions OIDC with branch-specific trust policy
resource "aws_iam_role" "github_actions" {
  name = "${var.repository_name}-github-actions-role"

  # Satisfies the DevOpsBound constraint in your AWS environment
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
          # Strict enforcement: only the main branch can assume this role
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:ref:refs/heads/main"
          }
        }
      }
    ]
  })
}

# 1. Define a custom, scoped policy for minimal permissions (Principle of Least Privilege)
resource "aws_iam_policy" "ecr_push_policy" {
  name        = "${var.repository_name}-ecr-push-policy"
  description = "Minimal permissions to push images to ${var.repository_name}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Required for 'docker login' to work (Global action)
        Action   = "ecr:GetAuthorizationToken"
        Effect   = "Allow"
        Resource = "*"
      },
      {
        # Specific actions needed to push a Docker image
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
        Effect = "Allow"
        # UPDATED: Reference to the new descriptive resource name
        Resource = aws_ecr_repository.service_repository.arn
      }
    ]
  })
}

# 2. Attach the custom minimal policy instead of broad managed policies
resource "aws_iam_role_policy_attachment" "ecr_policy" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.ecr_push_policy.arn
}

# 3. Lifecycle Policy to manage costs (Free Tier protection)
# This automatically deletes old images, keeping only the last 5.
resource "aws_ecr_lifecycle_policy" "cleanup_policy" {
  repository = aws_ecr_repository.service_repository.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only last 5 images to stay within Free Tier"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
