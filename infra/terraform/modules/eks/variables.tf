# ==============================================================================
# EKS MODULE – VARIABLES
# ==============================================================================

# --- Global Variables ---

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string

  validation {
    condition     = length(var.project_name) > 0
    error_message = "project_name must not be empty."
  }
}

variable "env" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string

  validation {
    condition     = length(var.env) > 0
    error_message = "env must not be empty."
  }
}

variable "account_id" {
  description = "AWS Account ID (used for permissions boundary and IAM ARNs)"
  type        = string

  validation {
    condition     = can(regex("^\\d{12}$", var.account_id))
    error_message = "account_id must be a non-empty 12-digit AWS account ID."
  }
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# --- Networking ---

variable "vpc_id" {
  description = "VPC ID where the EKS cluster will be deployed"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for EKS worker nodes"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs for the EKS control plane ENIs (enables kubectl from outside VPC)"
  type        = list(string)
  default     = []
}

# --- Cluster Configuration ---

variable "cluster_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.35"
}

variable "cluster_endpoint_public_access" {
  description = "Whether the EKS API endpoint is publicly accessible"
  type        = bool
  default     = true
}

variable "cluster_endpoint_private_access" {
  description = "Whether the EKS API endpoint is accessible from within the VPC"
  type        = bool
  default     = true
}

variable "enabled_cluster_log_types" {
  description = "List of EKS control plane log types to enable (api, audit, authenticator, controllerManager, scheduler)"
  type        = list(string)
  default     = ["audit"]
}

variable "cluster_log_retention_in_days" {
  description = "Number of days to retain EKS control plane logs in CloudWatch"
  type        = number
  default     = 7
}

# --- Node Group Configuration ---

variable "node_instance_types" {
  description = "List of EC2 instance types for the managed node group"
  type        = list(string)
  default     = ["t3.small"]
}

variable "node_desired_size" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 2
}

variable "node_min_size" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 2
}

variable "node_max_size" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 4
}

variable "node_disk_size" {
  description = "Disk size in GiB for worker nodes"
  type        = number
  default     = 20
}

variable "node_capacity_type" {
  description = "Capacity type for the node group (ON_DEMAND or SPOT)"
  type        = string
  default     = "ON_DEMAND"

  validation {
    condition     = contains(["ON_DEMAND", "SPOT"], var.node_capacity_type)
    error_message = "node_capacity_type must be ON_DEMAND or SPOT."
  }
}

variable "node_ami_type" {
  description = "AMI type for EKS worker nodes (AL2023_x86_64_STANDARD, AL2_x86_64, etc.)"
  type        = string
  default     = "AL2023_x86_64_STANDARD"
}

variable "node_subnet_ids" {
  description = "Subnet IDs for worker nodes. Defaults to private_subnet_ids when empty. Pass public_subnet_ids for NATless VPCs."
  type        = list(string)
  default     = []
}

variable "node_associate_public_ip_address" {
  description = "Assign a public IP to each worker node. Required when nodes are placed in public subnets in a NATless VPC."
  type        = bool
  default     = false
}
