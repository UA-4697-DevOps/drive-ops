output "repository_url" {
  description = "The URL of the ECR repository"
  value       = aws_ecr_repository.service_repository.repository_url
}

output "repository_arn" {
  description = "The ARN of the ECR repository"
  value       = aws_ecr_repository.service_repository.arn
}

output "role_arn" {
  description = "The ARN of the GitHub Actions IAM role"
  value       = aws_iam_role.role.arn
}

output "role_name" {
  description = "The name of the GitHub Actions IAM role (for attaching additional policies)"
  value       = aws_iam_role.role.name
}
