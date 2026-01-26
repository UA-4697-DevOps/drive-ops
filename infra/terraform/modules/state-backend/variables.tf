# --- Global Inputs ---

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
}

variable "env" {
  description = "Environment name (e.g., dev, prod)"
  type        = string
}

variable "cost_center" {
  description = "Cost center for billing and organization"
  type        = string
}

variable "enable_ha" {
  description = "Toggle for High Availability features"
  type        = bool
  default     = false
}

# --- Module Specific Inputs ---

variable "state_bucket_name" {
  description = "The name of the S3 bucket to store Terraform state"
  type        = string
}

variable "lock_table_name" {
  description = "The name of the DynamoDB table for state locking"
  type        = string
}

variable "tags" {
  description = "A map of tags to add to all resources"
  type        = map(string)
  default     = {}
}
