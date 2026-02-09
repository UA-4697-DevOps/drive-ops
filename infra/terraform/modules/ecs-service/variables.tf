# Required Variables

variable "service_name" {
  description = "Name of the ECS service (e.g., 'driver-service')"
  type        = string
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "env" {
  description = "Environment name (e.g., 'dev', 'prod')"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
}

# Network Configuration
variable "vpc_id" {
  description = "VPC ID where ECS service will run"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID for ECS tasks"
  type        = string
}


# Container Configuration

variable "ecr_repository_url" {
  description = "ECR repository URL (without tag)"
  type        = string
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

variable "container_port" {
  description = "Port the container listens on"
  type        = number
  default     = 8082
}

variable "container_cpu" {
  description = "CPU units for the container (1024 = 1 vCPU)"
  type        = number
  default     = 256
}

variable "container_memory" {
  description = "Memory in MB for the container"
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1
}

# Environment Variables & Secrets

variable "environment_variables" {
  description = "Map of environment variables to inject into the container"
  type        = map(string)
  default     = {}
}

variable "secrets" {
  description = "Map of secret ARNs to inject into the container"
  type = map(object({
    valueFrom = string
  }))
  default = {}
}

# ============================================================================
# IAM & Permissions
# ============================================================================

variable "sqs_queue_arns" {
  description = "List of SQS queue ARNs the service needs access to"
  type        = list(string)
  default     = []
}

variable "secrets_arns" {
  description = "List of Secrets Manager ARNs the service needs access to"
  type        = list(string)
  default     = []
}

# Health Check Configuration

variable "health_check_path" {
  description = "Health check endpoint path"
  type        = string
  default     = "/health"
}


# Tags
variable "tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}
