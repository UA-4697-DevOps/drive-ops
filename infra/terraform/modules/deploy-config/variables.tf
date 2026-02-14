
variable "project_name" {
  description = "The name of the project (e.g., drive-ops)"
  type        = string
}

variable "env" {
  description = "The deployment environment (e.g., dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for ARN construction"
  type        = string
}

variable "account_id" {
  description = "AWS account ID for ARN construction"
  type        = string
}

# --- Database Configuration (from RDS module outputs) ---

variable "db_host" {
  description = "RDS instance hostname (from rds module db_address output)"
  type        = string
}

variable "db_port" {
  description = "RDS instance port (from rds module db_port output)"
  type        = number
}

variable "db_name" {
  description = "Database name (from rds module db_name output)"
  type        = string
}

variable "db_user" {
  description = "Database master username (from rds module db_username output)"
  type        = string
  sensitive   = true
}

variable "rds_secret_arn" {
  description = "ARN of Secrets Manager secret containing RDS credentials (from secrets module)"
  type        = string
}

# --- SQS Queue URLs (from shared-infra module outputs) ---

variable "sqs_trip_created_url" {
  description = "SQS FIFO queue URL for trip-created events"
  type        = string
}

variable "sqs_driver_assigned_url" {
  description = "SQS FIFO queue URL for driver-assigned events"
  type        = string
}

variable "sqs_trip_completed_url" {
  description = "SQS FIFO queue URL for trip-completed events"
  type        = string
}

# --- ECR / GitHub Actions (from ecr module outputs) ---

variable "repository_name" {
  description = "ECR repository name (e.g., trip-service)"
  type        = string
}

variable "github_actions_role_name" {
  description = "Name of the existing GitHub Actions IAM role to attach deploy policy to"
  type        = string
}


# --- EC2 Instance ---

variable "ec2_instance_id" {
  description = "EC2 instance ID for SSM Run Command targeting"
  type        = string
}

# --- Tags ---

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# --- Global inputs from root.hcl (accepted but unused by this module) ---

variable "enable_ha" {
  description = "High availability flag (passed by root.hcl, unused here)"
  type        = bool
  default     = false
}

variable "cost_center" {
  description = "Cost center tag (passed by root.hcl, unused here)"
  type        = string
  default     = ""
}

variable "owner" {
  description = "Owner tag (passed by root.hcl, unused here)"
  type        = string
  default     = ""
}

