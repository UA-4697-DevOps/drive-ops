output "sns_topic_arn" {
  description = "The ARN of the SNS topic created for alerts"
  value       = aws_sns_topic.alerts.arn
}
