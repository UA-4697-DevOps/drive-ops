variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "env" {
  description = "Environment name (dev, staging, prod)"
  type        = string
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

# --- OpenVPN Configuration ---

variable "enable_openvpn" {
  description = "Install and configure OpenVPN server on the bastion host"
  type        = bool
  default     = false
}

variable "vpc_cidr" {
  description = "VPC CIDR block — pushed as a route to OpenVPN clients so they can reach private subnets"
  type        = string
  default     = ""
}

variable "vpn_client_cidr" {
  description = "CIDR block for the OpenVPN virtual network (tunnel addresses assigned to clients)"
  type        = string
  default     = "10.8.0.0/24"
}

variable "account_id" {
  description = "AWS account ID — used to scope least-privilege IAM policies to Secrets Manager ARNs for this account"
  type        = string
}

variable "aws_region" {
  description = "AWS region where the bastion is deployed — used in Secrets Manager ARNs and AWS CLI calls inside user_data"
  type        = string
  default     = "us-east-2"
}

variable "kms_key_arn" {
  description = "ARN of the customer-managed KMS key used to encrypt OpenVPN PKI and client-config secrets in Secrets Manager. Set to null to use the AWS-managed default key."
  type        = string
  default     = null

  validation {
    condition     = var.kms_key_arn == null || can(regex("^arn:aws:kms:", var.kms_key_arn))
    error_message = "kms_key_arn must be a valid KMS key ARN (arn:aws:kms:...) or null."
  }
}
