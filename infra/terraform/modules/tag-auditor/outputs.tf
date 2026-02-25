output "lambda_function_name" {
  description = "Name of the tag auditor Lambda function"
  value       = aws_lambda_function.tag_auditor.function_name
}

output "lambda_function_arn" {
  description = "ARN of the tag auditor Lambda function"
  value       = aws_lambda_function.tag_auditor.arn
}

output "cleanup_function_name" {
  description = "Name of the cleanup Lambda function"
  value       = aws_lambda_function.cleanup.function_name
}

output "cleanup_function_arn" {
  description = "ARN of the cleanup Lambda function"
  value       = aws_lambda_function.cleanup.arn
}
