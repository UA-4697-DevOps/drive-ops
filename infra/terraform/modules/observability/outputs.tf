output "monitoring_sns_topic_arn" {
  description = "The ARN of the central monitoring SNS topic"
  value       = module.sns.sns_topic_arn
}

output "notifier_lambda_function_name" {
  description = "The name of the Lambda function sending Discord alerts"
  # This matches the output name we just defined in Step 1
  value       = module.lambda_discord.lambda_function_name
}
