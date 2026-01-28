variable "project_name" {
  type        = string
  description = "The name of the project, used for naming resources (e.g., drive-ops)"
}

variable "env" {
  type        = string
  description = "The deployment environment (e.g., dev, staging, prod)"
}

variable "vpc_cidr" {
  type        = string
  default     = "10.0.0.0/16"
  description = "The CIDR block for the VPC"
}

variable "availability_zones" {
  type        = list(string)
  default     = ["us-east-2a", "us-east-2b"]
  description = "Fixed list of AZs to prevent infrastructure shuffling"

  validation {
    condition     = length(var.availability_zones) == 2
    error_message = "The availability_zones variable must contain exactly 2 AZs to match the subnet configuration."
  }
}
