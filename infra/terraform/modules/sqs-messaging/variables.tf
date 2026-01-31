# terraform/modules/sqs-messaging/variables.tf

# --- Global Variables ---

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

variable "enable_ha" {
  description = "Toggle for High Availability features across all queues"
  type        = bool
  default     = false
}

# --- Common Queue Settings ---

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

variable "common_tags" {
  description = "Common tags to apply to all queues"
  type        = map(string)
  default     = {}
}

# --- Per-Queue Visibility Timeouts ---

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
