# ==============================================================================
# EC2 INSTANCE MODULE – VARIABLES
# ==============================================================================

# --- Required ---

variable "name" {
  description = "Name for the EC2 instance (used in the Name tag and root volume tag)"
  type        = string

  validation {
    condition     = length(var.name) > 0
    error_message = "name must not be empty."
  }
}

variable "ami" {
  description = "AMI ID for the EC2 instance"
  type        = string

  validation {
    condition     = can(regex("^ami-[a-f0-9]{8,17}$", var.ami))
    error_message = "ami must be a valid AMI ID (e.g., ami-0abcdef1234567890)."
  }
}

variable "subnet_id" {
  description = "Subnet ID to launch the instance in"
  type        = string
}

variable "vpc_security_group_ids" {
  description = "List of security group IDs to attach to the instance"
  type        = list(string)

  validation {
    condition     = length(var.vpc_security_group_ids) > 0
    error_message = "At least one security group ID must be provided."
  }
}

# --- Optional: Compute ---

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "key_name" {
  description = "Name of an existing EC2 Key Pair for SSH access. null disables key-based SSH."
  type        = string
  default     = null
}

variable "iam_instance_profile" {
  description = "Name of the IAM instance profile to attach"
  type        = string
  default     = null
}

variable "monitoring" {
  description = "Enable detailed CloudWatch monitoring"
  type        = bool
  default     = false
}

variable "associate_public_ip_address" {
  description = "Associate a public IP address with the instance"
  type        = bool
  default     = false
}

variable "user_data" {
  description = "User data script to run on instance launch"
  type        = string
  default     = null
}

variable "disable_api_termination" {
  description = "Enable EC2 termination protection"
  type        = bool
  default     = false
}

variable "source_dest_check" {
  description = "Enable source/destination check. Set to false for NAT or VPN instances."
  type        = bool
  default     = true
}

# --- Optional: Metadata ---

variable "metadata_hop_limit" {
  description = "HTTP PUT response hop limit for IMDSv2. Use 1 for single-hop (bastion/NAT), 2 for containers."
  type        = number
  default     = 2

  validation {
    condition     = var.metadata_hop_limit >= 1 && var.metadata_hop_limit <= 64
    error_message = "metadata_hop_limit must be between 1 and 64."
  }
}

variable "instance_metadata_tags" {
  description = "Make instance tags accessible via the instance metadata service"
  type        = bool
  default     = true
}

# --- Optional: Storage ---

variable "root_volume_size" {
  description = "Size of the root EBS volume in GB"
  type        = number
  default     = 30

  validation {
    condition     = var.root_volume_size >= 8
    error_message = "root_volume_size must be at least 8 GB."
  }
}

variable "root_volume_type" {
  description = "Type of root EBS volume (gp3, gp2, io1, io2)"
  type        = string
  default     = "gp3"

  validation {
    condition     = contains(["gp3", "gp2", "io1", "io2"], var.root_volume_type)
    error_message = "root_volume_type must be one of: gp3, gp2, io1, io2."
  }
}

variable "root_volume_kms_key_id" {
  description = "ARN of a KMS key for root volume encryption. null uses the default AWS-managed EBS key."
  type        = string
  default     = null
}

variable "root_volume_iops" {
  description = "Amount of provisioned IOPS. Required for io1 and io2, optional for gp3."
  type        = number
  default     = null
}

variable "root_volume_throughput" {
  description = "Throughput in MiB/s. Only valid for gp3."
  type        = number
  default     = null
}

# --- Optional: Tags ---

variable "tags" {
  description = "Tags applied to the instance and root volume"
  type        = map(string)
  default     = {}
}

variable "extra_tags" {
  description = "Additional tags merged after var.tags (e.g., Role = NAT). Useful for consumer-specific metadata."
  type        = map(string)
  default     = {}
}
