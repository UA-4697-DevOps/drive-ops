variable "log_groups" {
  description = <<-EOT
    Map of log group configurations. Each entry must have:
      - name:              full CloudWatch log group name (e.g. /aws/eks/cluster)
      - retention_in_days: optional override for retention (falls back to var.retention_days)
      - kms_key_id:        optional KMS key ARN for encryption
  EOT

  type = map(object({
    name              = string
    retention_in_days = optional(number)
    kms_key_id        = optional(string)
  }))
}

variable "retention_days" {
  description = "Default retention in days applied to all log groups unless overridden per group"
  type        = number
  default     = 7
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
