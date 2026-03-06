variable "project_name" {
  type        = string
  description = "Project name (e.g., drive-ops)"
}

variable "env" {
  type        = string
  description = "Environment (e.g., dev, staging, prod)"
}

variable "service_name" {
  type        = string
  description = "Service name (e.g., driver-service)"
}

variable "namespace" {
  type        = string
  description = "Kubernetes namespace where ESO ServiceAccount lives"
  default     = "dev"
}

variable "oidc_provider_arn" {
  type        = string
  description = "ARN of the EKS OIDC provider"
}

variable "oidc_provider" {
  type        = string
  description = "OIDC provider URL without https:// prefix"
}

variable "secret_arns" {
  type        = list(string)
  description = "List of Secrets Manager ARNs that ESO is allowed to read"
}

variable "database_url" {
  type        = string
  description = "PostgreSQL connection string for the service"
  sensitive   = true
  default     = "placeholder"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
  default     = {}
}
