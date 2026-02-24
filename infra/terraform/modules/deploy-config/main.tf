# --- SSM Parameters (created via for_each from input map) ---

resource "aws_ssm_parameter" "this" {
  for_each = var.ssm_parameters

  name        = "/${var.project_name}/${var.env}/${each.key}"
  description = each.value.description
  type        = each.value.type
  value       = each.value.value

  tags = var.tags
}

# --- IAM Policy: Deploy Permissions for GitHub Actions ---

resource "aws_iam_policy" "deploy_policy" {
  name        = "${var.repository_name}-deploy-policy"
  description = "Permissions for deploying ${var.repository_name} via SSM Run Command"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SSMRunCommand"
        Effect = "Allow"
        Action = [
          "ssm:SendCommand",
          "ssm:GetCommandInvocation"
        ]
        Resource = [
          "arn:aws:ec2:${var.aws_region}:${var.account_id}:instance/${var.ec2_instance_id}",
          "arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript"
        ]
      },
      {
        Sid    = "SSMParameterRead"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParametersByPath"
        ]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/${var.project_name}/${var.env}/${var.service_name}/*",
          "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/${var.project_name}/${var.env}/sqs/*",
          "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/${var.project_name}/${var.env}/infra/*"
        ]
      },
      {
        Sid    = "SecretsManagerRead"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = var.rds_secret_arn
      },
      {
        Sid      = "ECRAuth"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid      = "ECRDescribe"
        Effect   = "Allow"
        Action   = ["ecr:DescribeImages"]
        Resource = var.ecr_repo_arn
      }
    ]
  })

  tags = var.tags
}

# Attach deploy policy to the existing GitHub Actions role
resource "aws_iam_role_policy_attachment" "deploy" {
  role       = var.github_actions_role_name
  policy_arn = aws_iam_policy.deploy_policy.arn
}
