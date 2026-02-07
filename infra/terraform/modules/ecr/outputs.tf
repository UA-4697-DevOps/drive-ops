output "repository_url" {
  value = aws_ecr_repository.service_repository.repository_url
}

output "role_arn" {
  value = aws_iam_role.github_actions.arn
}
