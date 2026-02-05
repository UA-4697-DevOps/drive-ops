variable "repository_name" {
  description = "The name of the ECR repository"
  type        = string
}

variable "account_id" {
  description = "The AWS Account ID where resources will be deployed"
  type        = string
}

variable "github_repo" {
  description = "The GitHub repository in 'org/repo' format (e.g., UA-4697-DevOps/drive-ops)"
  type        = string
}
