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

variable "node_subnet_ids" {
  description = "List of subnet IDs for EKS worker nodes. If not provided, private_subnet_ids will be used. Use this to deploy nodes to public subnets in NATless VPCs."
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
  description = "Whether the EKS API endpoint is publicly accessible"
  type        = bool
  default     = true
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "List of CIDR blocks allowed to access the public EKS API endpoint. Only applies when cluster_endpoint_public_access is true. Restrict to known IPs (e.g., bastion/VPN) for production. Set to [] to disable public access; must be explicitly set for public access."
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

variable "custom_security_group_rules" {
  description = "Additional custom security group rules to apply to the EKS cluster and nodes. Each rule must specify the security_group_id it applies to."
  type = map(object({
    type              = string           # "ingress" or "egress"
    from_port         = number
    to_port           = number
    protocol          = string           # "tcp", "udp", "-1" (all), etc.
    cidr_blocks       = optional(list(string))
    source_sg_id      = optional(string) # Security group ID (alternative to cidr_blocks)
    security_group_id = string           # Which SG to apply the rule to
    description       = string
  }))
  default = {}
}

variable "node_groups" {
  description = "Map of EKS managed node group configurations. Each node group can have different instance types, capacity types, scaling parameters, and disk sizes."
  type = map(object({
    instance_types         = list(string)
    ami_type               = string
    capacity_type          = string
    desired_size           = number
    min_size               = number
    max_size               = number
    disk_size              = number
    update_max_unavailable = number
    associate_public_ip    = bool
    tags                   = optional(map(string), {})
  }))
  default = {}
}
