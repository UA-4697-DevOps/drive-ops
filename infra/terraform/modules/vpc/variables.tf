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

variable "enable_flow_logs" {
  description = "Whether to enable VPC Flow Logs"
  type        = bool
  default     = false
}

variable "flow_log_retention_in_days" {
  description = "Number of days to retain VPC Flow Logs in CloudWatch"
  type        = number
  default     = 7
}

variable "account_id" {
  description = "The AWS Account ID"
  type        = string
}


variable "use_nat_instance" {
  description = "Whether to use a NAT Instance (fck-nat EC2) for private subnet outbound internet access. Defaults to false; must be set to true to enable outbound internet for private subnets."
  type        = bool
  default     = false
}

variable "nat_instance_type" {
  description = "Instance type for NAT Instance (t4g.nano recommended for cost optimization - ARM/Graviton)."
  type        = string
  default     = "t4g.nano"
  validation {
    condition = can(regex("^(?:t|m|c|r|a)\\d+g\\.[a-z0-9]+$", var.nat_instance_type))
    error_message = "nat_instance_type must be an ARM/Graviton family instance (e.g., t4g.nano, m6g.large). The NAT AMI lookup (data.aws_ami.nat_instance) is ARM64-only and will fail for x86 types like t3.nano."
  }
}

variable "nat_instance_key_name" {
  description = "Optional SSH key name for NAT Instance (for troubleshooting only). When null, SSH key access is disabled."
  type        = string
  default     = null
}

variable "nat_bastion_allowed_ssh_cidrs" {
  description = "List of CIDR blocks allowed to SSH to the NAT Instance (e.g., bastion security group CIDR). When empty, SSH ingress is not configured. Example: [\"10.0.1.0/24\"]"
  type        = list(string)
  default     = []
}

variable "enable_nat_instance_ssm" {
  description = "Whether to enable SSM Session Manager access to the NAT Instance (requires IAM instance profile)."
  type        = bool
  default     = true
}

variable "enable_nat_instance_cloudwatch" {
  description = "Whether to enable CloudWatch Agent on the NAT Instance for enhanced monitoring."
  type        = bool
  default     = true
}