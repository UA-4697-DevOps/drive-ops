variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "env" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "oidc_provider_arn" {
  description = "ARN of the EKS OIDC provider"
  type        = string
}

variable "oidc_provider_url" {
  description = "OIDC issuer URL without https:// prefix"
  type        = string
}

variable "node_role_arn" {
  description = "ARN of the EKS node IAM role (Karpenter needs iam:PassRole)"
  type        = string
}

variable "karpenter_version" {
  description = "Karpenter Helm chart version"
  type        = string
  default     = "1.3.3"
}

variable "tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}
