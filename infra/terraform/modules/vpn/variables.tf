variable "project_name" {
  type        = string
  description = "Project name used for resource naming (e.g., drive-ops)"
}

variable "env" {
  type        = string
  description = "Deployment environment (dev, staging, prod)"
}

variable "account_id" {
  type        = string
  description = "AWS Account ID — used to scope Secrets Manager IAM policy ARNs"
}

variable "aws_region" {
  type        = string
  description = "AWS region where the VPN server is deployed — used in Secrets Manager ARNs and AWS CLI calls in user_data"
  default     = "us-east-2"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID where the VPN instance will be deployed"
}

variable "public_subnet_id" {
  type        = string
  description = "ID of a public subnet for the VPN instance (must have an Internet Gateway route for clients to reach it)"
}

variable "instance_type" {
  type        = string
  default     = "t4g.micro"
  description = "EC2 instance type for the VPN server. t4g.micro is recommended — OpenVPN's AES-256-GCM cipher uses hardware acceleration on Graviton."
}

variable "key_name" {
  type        = string
  default     = null
  description = "Optional EC2 Key Pair name for SSH break-glass access. When null, use SSM Session Manager instead."
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block — pushed as a static route to VPN clients so they can reach all private subnet resources"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "vpc_cidr must be a valid CIDR block (e.g., 10.0.0.0/16)."
  }
}

variable "vpn_client_cidr" {
  type        = string
  default     = "10.8.0.0/24"
  description = "CIDR block for the OpenVPN virtual network — tunnel IPs assigned to connecting clients (must not overlap with vpc_cidr)"

  validation {
    condition     = can(cidrhost(var.vpn_client_cidr, 0))
    error_message = "vpn_client_cidr must be a valid CIDR block (e.g., 10.8.0.0/24)."
  }
}

variable "allowed_vpn_cidrs" {
  type        = list(string)
  description = "List of CIDR blocks allowed to connect to the OpenVPN server on UDP 1194. Example: [\"203.0.113.10/32\"]"

  validation {
    condition     = length(var.allowed_vpn_cidrs) > 0
    error_message = "allowed_vpn_cidrs must contain at least one CIDR block. An empty allowlist means nobody can connect."
  }

  validation {
    condition     = !contains(var.allowed_vpn_cidrs, "0.0.0.0/0") && !contains(var.allowed_vpn_cidrs, "::/0")
    error_message = "0.0.0.0/0 and ::/0 are forbidden — use specific IPs or ranges to restrict VPN access."
  }
}

variable "kms_key_arn" {
  type        = string
  default     = null
  description = "ARN of a customer-managed KMS key for encrypting OpenVPN PKI and client-config secrets in Secrets Manager. Set to null to use the AWS-managed default key."

  validation {
    condition     = var.kms_key_arn == null || can(regex("^arn:aws:kms:", var.kms_key_arn))
    error_message = "kms_key_arn must be a valid KMS key ARN (arn:aws:kms:...) or null."
  }
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Additional tags applied to all VPN resources"
}
