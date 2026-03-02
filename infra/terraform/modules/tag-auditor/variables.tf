variable "project_name" {
  description = "Project name"
  type        = string
}

variable "env" {
  description = "Environment (dev, prod, etc.)"
  type        = string
}

variable "account_id" {
  description = "AWS Account ID"
  type        = string
}

variable "sns_topic_arn" {
  description = "SNS Topic ARN for notifications"
  type        = string
}

variable "lambda_functions" {
  description = "Map of Lambda functions configuration"
  type = map(object({
    handler     = string
    runtime     = optional(string, "python3.12")
    timeout     = optional(number, 60)
    memory_size = optional(number, 128)
    schedule    = optional(string, null) # If null, no schedule will be created
    description = optional(string, "Managed by Terraform")
  }))
  
  # Default values so the module works out of the box
  default = {
    "tag-auditor" = {
      handler     = "tag_auditor.lambda_handler"
      description = "Audits resources for tagging compliance"
      schedule    = "rate(24 hours)"
    },
    "tag-cleanup" = {
      handler     = "cleanup.lambda_handler"
      description = "Terminates non-compliant resources"
    }
  }
}
