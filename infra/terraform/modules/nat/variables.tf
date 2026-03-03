variable "enabled" {
  type        = bool
  default     = false
  description = "Set to true to provision the NAT instance. false by default — the stack is a no-op unless explicitly enabled."
}

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
  description = "AWS Account ID — used to construct the IAM permissions boundary ARN"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID where the NAT instance will be deployed"
}

variable "public_subnet_id" {
  type        = string
  description = "ID of a public subnet where the NAT instance is placed (must have IGW route)"
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks of private subnets — whitelisted for inbound NAT forwarding traffic"
}

variable "private_route_table_id" {
  type        = string
  description = "ID of the private route table — this module adds a 0.0.0.0/0 route pointing to the NAT instance"
}

variable "instance_type" {
  type        = string
  default     = "t4g.nano"
  description = "EC2 instance type for the NAT instance. Must be an ARM/Graviton type — the fck-nat AMI is ARM64-only."

  validation {
    condition     = can(regex("^(?:t|m|c|r|a)\\d+g\\.[a-z0-9]+$", var.instance_type))
    error_message = "instance_type must be an ARM/Graviton family instance (e.g., t4g.nano, m6g.large). x86 types like t3.nano are not compatible with the fck-nat ARM64 AMI."
  }
}

variable "key_name" {
  type        = string
  default     = null
  description = "Optional EC2 Key Pair name for SSH break-glass access. When null, key-based SSH is disabled (use SSM Session Manager instead)."
}

variable "allowed_ssh_cidrs" {
  type        = list(string)
  default     = []
  description = "List of CIDR blocks allowed to SSH to the NAT instance (e.g., bastion public IP). When empty, SSH ingress is not configured. Example: [\"10.0.1.10/32\"]"

  validation {
    condition     = alltrue([for cidr in var.allowed_ssh_cidrs : can(cidrhost(cidr, 0))])
    error_message = "Each entry in allowed_ssh_cidrs must be a valid CIDR block."
  }

  validation {
    condition     = !contains(var.allowed_ssh_cidrs, "0.0.0.0/0") && !contains(var.allowed_ssh_cidrs, "::/0")
    error_message = "0.0.0.0/0 and ::/0 are not allowed for SSH ingress. Use specific source CIDRs."
  }
}

variable "enable_ssm" {
  type        = bool
  default     = true
  description = "Attach AmazonSSMManagedInstanceCore so the NAT instance can be reached via Session Manager without opening port 22."
}

variable "enable_cloudwatch" {
  type        = bool
  default     = true
  description = "Attach CloudWatchAgentServerPolicy to enable enhanced instance monitoring (NAT throughput, errors, etc.)."
}
