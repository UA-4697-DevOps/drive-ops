# --- SSM Parameters: Database Configuration ---

resource "aws_ssm_parameter" "db_host" {
  name        = "/${var.project_name}/${var.env}/trip-service/db-host"
  description = "RDS endpoint hostname for TripService"
  type        = "String"
  value       = var.db_host

  tags = var.tags
}

resource "aws_ssm_parameter" "db_port" {
  name        = "/${var.project_name}/${var.env}/trip-service/db-port"
  description = "RDS port for TripService"
  type        = "String"
  value       = tostring(var.db_port)

  tags = var.tags
}

resource "aws_ssm_parameter" "db_name" {
  name        = "/${var.project_name}/${var.env}/trip-service/db-name"
  description = "Database name for TripService"
  type        = "String"
  value       = var.db_name

  tags = var.tags
}

resource "aws_ssm_parameter" "db_user" {
  name        = "/${var.project_name}/${var.env}/trip-service/db-user"
  description = "Database username for TripService"
  type        = "SecureString"
  value       = var.db_user

  tags = var.tags
}

# --- SSM Parameters: SQS Queue URLs ---

resource "aws_ssm_parameter" "sqs_trip_created_url" {
  name        = "/${var.project_name}/${var.env}/sqs/trip-created-url"
  description = "SQS FIFO queue URL for trip-created events"
  type        = "String"
  value       = var.sqs_trip_created_url

  tags = var.tags
}

resource "aws_ssm_parameter" "sqs_driver_assigned_url" {
  name        = "/${var.project_name}/${var.env}/sqs/driver-assigned-url"
  description = "SQS FIFO queue URL for driver-assigned events"
  type        = "String"
  value       = var.sqs_driver_assigned_url

  tags = var.tags
}

resource "aws_ssm_parameter" "sqs_trip_completed_url" {
  name        = "/${var.project_name}/${var.env}/sqs/trip-completed-url"
  description = "SQS FIFO queue URL for trip-completed events"
  type        = "String"
  value       = var.sqs_trip_completed_url

  tags = var.tags
}

# --- SSM Parameter: EC2 Instance ID (for SSM Run Command targeting) ---

resource "aws_ssm_parameter" "ec2_instance_id" {
  name        = "/${var.project_name}/${var.env}/infra/ec2-instance-id"
  description = "EC2 instance ID for SSM Run Command targeting"
  type        = "String"
  value       = var.ec2_instance_id

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
        Resource = "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/${var.project_name}/${var.env}/*"
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
        Sid    = "ECRImagePull"
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
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
