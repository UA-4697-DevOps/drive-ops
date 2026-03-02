output "lambda_function_name" {
  description = "Name of the tag-auditor Lambda function"
  value       = aws_lambda_function.this["tag-auditor"].function_name
}

output "lambda_function_arn" {
  description = "ARN of the tag-auditor Lambda function"
  value       = aws_lambda_function.this["tag-auditor"].arn
}

output "cleanup_function_name" {
  description = "Name of the tag-cleanup Lambda function"
  value       = aws_lambda_function.this["tag-cleanup"].function_name
}

output "cleanup_function_arn" {
  description = "ARN of the tag-cleanup Lambda function"
  value       = aws_lambda_function.this["tag-cleanup"].arn
}

# Додатковий output, який повертає всі функції списком (корисно для майбутнього масштабування)
output "all_lambda_functions" {
  description = "Map of all created Lambda functions"
  value       = { for k, v in aws_lambda_function.this : k => v.arn }
}
