output "lambda_function_name" {
  description = "The name of the Lambda function"
  # Changed from 'this' to 'discord_notifier' to match main.tf
  value       = aws_lambda_function.discord_notifier.function_name
}

output "lambda_function_arn" {
  description = "The ARN of the Lambda function"
  value       = aws_lambda_function.discord_notifier.arn
}
