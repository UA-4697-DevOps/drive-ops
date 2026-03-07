# ==============================================================================
# AWS LOAD BALANCER CONTROLLER – VARIABLES
# ==============================================================================

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

variable "oidc_provider_arn" {
  description = "ARN of the OIDC identity provider"
  type        = string
}

variable "oidc_provider_url" {
  description = "OIDC issuer URL without the https:// prefix"
  type        = string
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace where the controller will run"
  type        = string
  default     = "kube-system"
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}
