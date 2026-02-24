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

variable "cluster_name_prefix" {
  description = "Prefix for the EKS cluster name. Override to customise the naming convention."
  type        = string
  default     = "Training-"
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
  description = <<-EOT
    Kubernetes version for the EKS cluster.
    NOTE (v1.35+): cgroup v1 is deprecated; nodes using cgroup v1 may fail to
    start. AL2023 (the default AMI) uses cgroup v2, so no action is needed for
    the default AMI. Custom AMIs must be migrated to cgroup v2 before upgrading.
    Also consider evaluating a migration from Ingress NGINX (retired) to Gateway
    API or an alternative ingress controller.
  EOT
  type        = string
  default     = "1.35"
}

variable "cluster_endpoint_public_access" {
  description = <<-EOT
    Whether the EKS API endpoint is publicly accessible.
    
    **BREAKING CHANGE:** The default is now `false` (was `true`).
    If you require public access, set `cluster_endpoint_public_access = true` and specify trusted CIDRs in `cluster_endpoint_public_access_cidrs`.
    
    See CHANGELOG.md for migration details.
    
    Defaults to false for security (private-only access via VPC/bastion). Set to true ONLY if you explicitly set cluster_endpoint_public_access_cidrs to trusted IPs.
  EOT
  type        = bool
  default     = false
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "List of CIDR blocks allowed to access the public EKS API endpoint. REQUIRED when cluster_endpoint_public_access is true. Must NOT be empty when enabling public access — set to specific IPs (e.g., bastion/VPN) to restrict access. Default empty list enforces private-only access."
  type        = list(string)
  default     = []
}

variable "cluster_endpoint_private_access" {
  description = "Whether the EKS API endpoint is accessible from within the VPC"
  type        = bool
  default     = true
}

variable "enabled_cluster_log_types" {
  description = "List of EKS control plane log types to enable (api, audit, authenticator, controllerManager, scheduler)"
  type        = list(string)
  default     = ["audit", "api", "authenticator"]
}

variable "cluster_log_retention_in_days" {
  description = "Number of days to retain EKS control plane logs in CloudWatch"
  type        = number
  default     = 7
}

variable "kms_key_arn" {
  description = "ARN of the customer-managed KMS key used to encrypt EKS secrets (encryption_config) and the CloudWatch log group. Set to null to disable envelope encryption. Must be a key ARN (arn:aws:kms:...), not an alias ARN."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.kms_key_arn == null || (!can(regex(":alias/", var.kms_key_arn)) && can(regex("^arn:aws:kms:", var.kms_key_arn)))
    error_message = "kms_key_arn must be a key ARN (e.g., arn:aws:kms:region:account:key/id), not an alias ARN (e.g., arn:aws:kms:region:account:alias/...). Set to null to disable encryption."
  }
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

  validation {
    condition = contains([
      "AL2023_x86_64_STANDARD",
      "AL2023_ARM_64_STANDARD",
      "AL2023_x86_64_NEURON",
      "AL2023_x86_64_NVIDIA",
      "AL2023_ARM_64_NVIDIA",
      "AL2_x86_64",
      "AL2_x86_64_GPU",
      "AL2_ARM_64",
      "BOTTLEROCKET_ARM_64",
      "BOTTLEROCKET_x86_64",
      "BOTTLEROCKET_ARM_64_FIPS",
      "BOTTLEROCKET_x86_64_FIPS",
      "BOTTLEROCKET_x86_64_NVIDIA",
      "BOTTLEROCKET_ARM_64_NVIDIA",
      "BOTTLEROCKET_ARM_64_NVIDIA_FIPS",
      "BOTTLEROCKET_x86_64_NVIDIA_FIPS",
      "WINDOWS_CORE_2022_x86_64",
      "WINDOWS_CORE_2019_x86_64",
      "WINDOWS_FULL_2019_x86_64",
      "WINDOWS_CORE_2025_x86_64",
      "WINDOWS_FULL_2022_x86_64",
      "WINDOWS_FULL_2025_x86_64",
      "CUSTOM"
    ], var.node_ami_type)
    error_message = "Invalid node_ami_type: must be one of AL2023_x86_64_STANDARD, AL2023_ARM_64_STANDARD, AL2023_x86_64_NEURON, AL2023_x86_64_NVIDIA, AL2023_ARM_64_NVIDIA, AL2_x86_64, AL2_x86_64_GPU, AL2_ARM_64, BOTTLEROCKET_ARM_64, BOTTLEROCKET_x86_64, BOTTLEROCKET_ARM_64_FIPS, BOTTLEROCKET_x86_64_FIPS, BOTTLEROCKET_x86_64_NVIDIA, BOTTLEROCKET_ARM_64_NVIDIA, BOTTLEROCKET_ARM_64_NVIDIA_FIPS, BOTTLEROCKET_x86_64_NVIDIA_FIPS, WINDOWS_CORE_2022_x86_64, WINDOWS_CORE_2019_x86_64, WINDOWS_FULL_2019_x86_64, WINDOWS_CORE_2025_x86_64, WINDOWS_FULL_2022_x86_64, WINDOWS_FULL_2025_x86_64, or CUSTOM."
  }
}

variable "node_subnet_ids" {
  description = "Subnet IDs for worker nodes. Defaults to private_subnet_ids when empty. Pass public_subnet_ids for NATless VPCs (nodes in public subnets)."
  type        = list(string)
  default     = []
}

variable "node_associate_public_ip_address" {
  description = "Assign a public IP to each worker node. Required when nodes are placed in public subnets without a NAT Instance."
  type        = bool
  default     = false
}

variable "node_update_max_unavailable" {
  description = "Maximum number of worker nodes that can be unavailable during node group updates. Configurable to support different availability and update strategies."
  type        = number
  default     = 1

  validation {
    condition     = var.node_update_max_unavailable >= 1
    error_message = "node_update_max_unavailable must be at least 1."
  }
}

variable "bastion_sg_id" {
  description = "Security group ID of the bastion host. When set, adds an ingress rule on port 22 to the node security group so engineers can SSH from the bastion to worker nodes for debugging. Set to null to omit the rule (use SSM Session Manager instead)."
  type        = string
  default     = null
  nullable    = true
}

variable "kubelet_extra_args" {
  description = <<-EOT
    Extra arguments to pass to the kubelet on worker nodes (e.g., --fail-swap-on=false).
    
    For Kubernetes v1.35+ with cgroup v1 compatibility fallback, set `failCgroupV1: false` in the kubelet ConfigMap (`kube-system/kubelet-config`).
    Do not use a `--fail-cgroup-v1` CLI flag (it does not exist and will not be recognized by kubelet or bootstrap.sh).
    This is only needed for custom AMIs that do not support cgroup v2. AL2023 and Bottlerocket node images use cgroup v2 and nodeadm by default and do not require this setting.
  EOT
  type        = string
  default     = ""
}