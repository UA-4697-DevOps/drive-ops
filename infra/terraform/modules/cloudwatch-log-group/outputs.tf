output "log_group_arns" {
  description = "Map of log group ARNs keyed by the input map key"
  value       = { for k, v in aws_cloudwatch_log_group.this : k => v.arn }
}

output "log_group_names" {
  description = "Map of log group names keyed by the input map key"
  value       = { for k, v in aws_cloudwatch_log_group.this : k => v.name }
}
