# ============================================================================
# Project and Environment Variables
# ============================================================================

variable "project_name" {
  type        = string
  description = "The name of the project, used for naming resources (e.g., drive-ops)"
}

variable "env" {
  type        = string
  description = "The deployment environment (e.g., dev, staging, prod). Used for resource naming and tagging."
}

# ============================================================================
# Database Configuration
# ============================================================================

variable "db_name" {
  type        = string
  description = "The name of the default database to create when the RDS instance is created. Must begin with a letter and contain only alphanumeric characters."
}

variable "master_username" {
  type        = string
  description = "Username for the master DB user. Cannot be 'admin', 'root', 'rdsadmin', or other reserved words."
  default     = "postgres"
}

# ============================================================================
# Network Configuration (from VPC module)
# ============================================================================

variable "vpc_id" {
  type        = string
  description = "The ID of the VPC where RDS will be deployed. Used for resource tagging and validation."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "List of private subnet IDs spanning at least 2 availability zones for the DB subnet group. Required for Multi-AZ and high availability."
  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "private_subnet_ids must include at least two subnets in different AZs."
  }
}

variable "db_security_group_id" {
  type        = string
  description = "Security group ID for database access control (sg-db). Should only allow inbound PostgreSQL traffic (port 5432) from application security group."
}

# ============================================================================
# Engine Configuration
# ============================================================================

variable "engine" {
  type        = string
  description = "The database engine to use. Must be 'postgres' for PostgreSQL."
  default     = "postgres"

  validation {
    condition     = var.engine == "postgres"
    error_message = "Only 'postgres' engine is supported by this module."
  }
}

variable "engine_version" {
  type        = string
  description = "PostgreSQL engine version (e.g., '15.8', '16.1'). Refer to AWS documentation for available versions. Newer versions include security patches and performance improvements."
  default     = "15.15"
}

# ============================================================================
# Instance Sizing and Storage
# ============================================================================

variable "instance_class" {
  type        = string
  description = "The instance type of the RDS instance (e.g., db.t3.micro, db.t3.small, db.r6g.large). Controls CPU, memory, and network performance. Use t3.micro for dev, t3.medium+ for prod."
  default     = "db.t3.micro"

  validation {
    condition     = var.instance_class == "db.t3.micro" || var.instance_class == "db.t4g.micro"
    error_message = "We are allow to use only Free Tier instances."
  }
}

variable "allocated_storage" {
  type        = number
  description = "The allocated storage size in gigabytes. Minimum is 20 GB for gp3 storage type. Can be scaled up later without downtime."
  default     = 20

  validation {
    condition     = var.allocated_storage >= 20 && var.allocated_storage <= 65536
    error_message = "Allocated storage must be between 20 GB and 65536 GB (64 TB)."
  }
}

# ============================================================================
# High Availability and Disaster Recovery
# ============================================================================

variable "multi_az" {
  type        = bool
  description = "Specifies if the RDS instance should be Multi-AZ for high availability. Maintains a standby replica in a different availability zone. Set to false for dev (cost savings), true for prod."
  default     = false
}

variable "backup_retention_period" {
  type        = number
  description = "The number of days to retain automated backups (0-35). Set to 0 to disable backups. Recommended: 1 day for dev, 7-30 days for prod."
  default     = 1

  validation {
    condition     = var.backup_retention_period >= 0 && var.backup_retention_period <= 35
    error_message = "Backup retention period must be between 0 and 35 days."
  }
}

variable "skip_final_snapshot" {
  type        = bool
  description = "Determines whether a final DB snapshot is created before deletion. Set to true for dev (faster cleanup), false for prod (safety)."
  default     = true
}

variable "final_snapshot_identifier" {
  type        = string
  description = "The name of the final DB snapshot when skip_final_snapshot is false. If empty and skip_final_snapshot is false, a default name will be generated."
  default     = ""
}

# ============================================================================
# Security and Protection
# ============================================================================

variable "deletion_protection" {
  type        = bool
  description = "If true, prevents the database from being deleted accidentally. Must be disabled before destroying the resource. Set to false for dev, true for prod."
  default     = false
}

# ============================================================================
# Optional Performance Features
# ============================================================================

variable "enable_performance_insights" {
  type        = bool
  description = "Enable Performance Insights for advanced database performance monitoring and analysis. Adds additional cost (~$0.18/vCPU/month). Recommended for prod troubleshooting."
  default     = false
}

variable "performance_insights_retention_period" {
  type        = number
  description = "The number of days to retain Performance Insights data (7 or 731). Only used if enable_performance_insights is true. 7 days is free tier, 731 days adds cost."
  default     = 7

  validation {
    condition     = contains([7, 731], var.performance_insights_retention_period)
    error_message = "Performance Insights retention period must be either 7 or 731 days."
  }
}

# ============================================================================
# Security and Debugging Options
# ============================================================================

variable "expose_master_password" {
  type        = bool
  description = "SECURITY WARNING: If true, exposes the master password as a Terraform output. This can leak credentials through CI logs, state files, and console output. Should ONLY be enabled for local debugging and NEVER in production. Applications should always retrieve passwords from AWS Secrets Manager instead. Default: false (disabled for security)."
  default     = false
}

variable "tags" {
  description = "A map of tags to apply to the DB resource"
  type        = map(string)
  default     = {}
}
