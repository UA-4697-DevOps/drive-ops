# terraform/modules/shared-infra/variables.tf

# --- Global Variables ---

variable "account_id" {
  type        = string
  description = "AWS Account ID passed from Terragrunt"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
}

variable "env" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
}

variable "cost_center" {
  description = "Cost center for billing and organization"
  type        = string
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# --- VPC Variables ---
variable "vpc_cidr" {
  description = "The CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Fixed list of AZs to prevent infrastructure shuffling"
  type        = list(string)
  default     = ["us-east-2a", "us-east-2b"]
}

variable "enable_flow_logs" {
  description = "Whether to enable VPC Flow Logs"
  type        = bool
  default     = false
}

variable "flow_log_retention_in_days" {
  description = "Number of days to retain VPC Flow Logs in CloudWatch"
  type        = number
  default     = 7
}

# --- SQS Variables ---
variable "enable_ha" {
  description = "Toggle for High Availability features across all queues"
  type        = bool
  default     = false
}

variable "message_retention" {
  description = "Message retention period in seconds (default: 4 days)"
  type        = number
  default     = 345600
}

variable "max_receive_count" {
  description = "Maximum receives before sending to DLQ"
  type        = number
  default     = 3
}

variable "trip_created_visibility_timeout" {
  description = "Visibility timeout for trip-created queue in seconds"
  type        = number
  default     = 60
}

variable "driver_assigned_visibility_timeout" {
  description = "Visibility timeout for driver-assigned queue in seconds"
  type        = number
  default     = 60
}

variable "trip_completed_visibility_timeout" {
  description = "Visibility timeout for trip-completed queue in seconds"
  type        = number
  default     = 60
}
