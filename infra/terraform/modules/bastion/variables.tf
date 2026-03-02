variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "env" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "account_id" {
  description = "AWS Account ID — used for the DevOpsBound permissions boundary on the bastion IAM role"
  type        = string

  validation {
    condition     = can(regex("^\\d{12}$", var.account_id))
    error_message = "account_id must be a 12-digit AWS account ID."
  }
}

variable "vpc_id" {
  description = "VPC ID where the bastion will be deployed"
  type        = string
}

variable "public_subnet_id" {
  description = "Public subnet ID for the bastion host"
  type        = string
}

variable "key_name" {
  description = "Name of an existing EC2 Key Pair for SSH access"
  type        = string
}

variable "allowed_ssh_cidrs" {
  description = <<-EOT
    List of CIDR blocks allowed to SSH into the bastion.
    Example: ["203.0.113.10/32", "198.51.100.0/24"]
    NEVER use "0.0.0.0/0" — that defeats the purpose of a bastion.
  EOT
  type        = list(string)

  validation {
    condition     = length(var.allowed_ssh_cidrs) > 0
    error_message = "allowed_ssh_cidrs must contain at least one CIDR block. An empty allowlist means nobody can connect."
  }

  validation {
    condition     = !contains(var.allowed_ssh_cidrs, "0.0.0.0/0") && !contains(var.allowed_ssh_cidrs, "::/0")
    error_message = "Neither 0.0.0.0/0 nor ::/0 is allowed — use specific IPs or ranges for SSH access. Wildcard IPv4 and IPv6 CIDRs are forbidden."
  }
}

variable "instance_type" {
  description = "EC2 instance type for the bastion host (t4g.nano recommended - ARM/Graviton)"
  type        = string
  default     = "t4g.nano"
}

variable "tags" {
  description = "Additional tags applied to all bastion resources"
  type        = map(string)
  default     = {}
}


