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
  value       = module.ci_role.iam_role_arn
}

output "role_name" {
  description = "The name of the GitHub Actions IAM role (for attaching additional policies)"
  value       = module.ci_role.iam_role_name
}

output "deploy_role_arn" {
  description = "The ARN of the GitHub Actions deploy IAM role (workflow_dispatch)"
  value       = module.deploy_role.iam_role_arn
}

output "deploy_role_name" {
  description = "The name of the GitHub Actions deploy IAM role"
  value       = module.deploy_role.iam_role_name
}
