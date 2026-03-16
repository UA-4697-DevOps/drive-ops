variable "role_name" {
  description = "Name of the IAM role"
  type        = string
}

variable "role_description" {
  description = "Description of the IAM role"
  type        = string
  default     = null
}

variable "assume_role_policy" {
  description = "IAM policy document that restricts who can assume this role (JSON)"
  type        = string
}

variable "create_instance_profile" {
  description = "Whether to create an IAM instance profile (often used for EC2)"
  type        = bool
  default     = false
}

variable "managed_policy_arns" {
  description = "List of existing/managed IAM policy ARNs to attach to the role"
  type        = list(string)
  default     = []
}

variable "custom_policies" {
  description = "Map of custom policy names and their JSON documents to create and attach"
  type        = map(string)
  default     = {}
}

variable "inline_policies" {
  description = "Map of inline policy names and their JSON documents to attach directly to the role"
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "A mapping of tags to assign to all resources"
  type        = map(string)
  default     = {}
}
