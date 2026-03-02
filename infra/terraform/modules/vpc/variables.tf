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

# --- NAT Instance Variables ---

variable "use_nat_instance" {
  description = "Whether to deploy a NAT instance (fck-nat) for private subnet outbound internet access. Cost-effective alternative to AWS NAT Gateway."
  type        = bool
  default     = false
}

variable "nat_instance_type" {
  description = "EC2 instance type for the NAT instance. t4g.nano is sufficient for most workloads (ARM64/Graviton)."
  type        = string
  default     = "t4g.nano"
}

variable "nat_instance_key_name" {
  description = "Name of the EC2 key pair to associate with the NAT instance. Leave empty to use SSM Session Manager only."
  type        = string
  default     = null
}

variable "enable_nat_instance_ssm" {
  description = "Whether to attach the AmazonSSMManagedInstanceCore policy to allow Session Manager access to the NAT instance."
  type        = bool
  default     = true
}

variable "enable_nat_instance_cloudwatch" {
  description = "Whether to attach the CloudWatchAgentServerPolicy to enable CloudWatch monitoring on the NAT instance."
  type        = bool
  default     = false
}

variable "nat_bastion_allowed_ssh_cidrs" {
  description = "List of CIDR blocks allowed to SSH into the NAT instance. Leave empty to disable SSH access."
  type        = list(string)
  default     = []
}

