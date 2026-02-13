variable "project_name" {
  type        = string
  description = "The name of the project, used for naming resources (e.g., drive-ops)"
}

variable "env" {
  type        = string
  description = "The deployment environment (e.g., dev, staging, prod). Used for resource naming and tagging."
}

variable "db_identifier" {
  type        = string
  description = "DB identifier"
}

variable "tags" {
  description = "A map of tags to apply to the Secrets Manager resource"
  type        = map(string)
  default     = {}
}

variable "rds_master_username" {
  type        = string
  description = "The name of the default database to create when the RDS instance is created. Must begin with a letter or underscore and contain only alphanumeric characters or underscores."

  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9_]{0,15}$", var.rds_master_username)) && !contains(["admin", "root", "rdsadmin", "postgres"], lower(var.rds_master_username))
    error_message = "rds_master_username must be 1-16 characters, start with a letter, contain only alphanumeric characters and underscores, and not be a reserved word."
  }
}

variable "discord_webhook_url" {
  type        = string
  description = "The Discord webhook URL for notifications"
  sensitive   = true # Ensures the value is hidden in CLI output
}
