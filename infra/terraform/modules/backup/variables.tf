variable "project_name" {
  description = "The name of the project"
  type        = string
}

variable "env" {
  description = "The environment (e.g., dev, prod)"
  type        = string
}

variable "eks_oidc_provider_arn" {
  description = "The ARN of the EKS OIDC Provider"
  type        = string
}

variable "eks_oidc_provider_url" {
  description = "The URL of the EKS OIDC Provider"
  type        = string
}

variable "k8s_namespace" {
  description = "The Kubernetes namespace where the CronJob will run"
  type        = string
  default     = "default"
}

variable "k8s_service_account_name" {
  description = "The name of the Kubernetes Service Account"
  type        = string
  default     = "db-backup-sa"
}

variable "backup_kms_key_arn" {
  description = "The ARN of the KMS key used to encrypt the backup S3 bucket"
  type        = string
}
