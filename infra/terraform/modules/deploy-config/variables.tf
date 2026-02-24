
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

# --- SSM Parameters (DRY: single map drives all SSM resources) ---

variable "ssm_parameters" {
  description = <<-EOT
    Map of SSM parameters to create. Each key is the parameter path suffix
    (appended to /<project_name>/<env>/), and the value is an object with:
      - description: Human-readable description of the parameter
      - type:        SSM parameter type ("String" or "SecureString")
      - value:       The parameter value
  EOT

  type = map(object({
    description = string
    type        = string
    value       = string
  }))
}

# --- IAM / Deploy Configuration ---

variable "rds_secret_arn" {
  description = "ARN of Secrets Manager secret containing RDS credentials (from secrets module)"
  type        = string
}

variable "repository_name" {
  description = "ECR repository name (e.g., trip-service)"
  type        = string
}

variable "ecr_repo_arn" {
  description = "ARN of the ECR repository (for scoping DescribeImages permission)"
  type        = string
}

variable "github_actions_role_name" {
  description = "Name of the existing GitHub Actions IAM role to attach deploy policy to"
  type        = string
}

variable "service_name" {
  description = "Service name used to scope SSM parameter read paths in IAM (e.g., trip-service)"
  type        = string
}

variable "ec2_instance_id" {
  description = "EC2 instance ID for SSM Run Command IAM scoping"
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
