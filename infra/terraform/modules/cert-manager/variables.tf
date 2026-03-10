# ==============================================================================
# CERT-MANAGER – VARIABLES
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
  description = "OIDC issuer URL without the https:// prefix (e.g., 'oidc.eks.us-east-2.amazonaws.com/id/EXAMPLEID')"
  type        = string

  validation {
    condition     = !startswith(var.oidc_provider_url, "http://") && !startswith(var.oidc_provider_url, "https://") && !endswith(var.oidc_provider_url, "/")
    error_message = "oidc_provider_url must not start with 'http://' or 'https://' and must not end with '/'. Pass the issuer host only (e.g., 'oidc.eks.us-east-2.amazonaws.com/id/EXAMPLEID')."
  }
}

variable "zone_id" {
  description = "Route53 hosted zone ID"
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace where cert-manager is deployed"
  type        = string
  default     = "cert-manager"
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
