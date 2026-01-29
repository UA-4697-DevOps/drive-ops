# ============================================================================
# RDS Instance Outputs
# ============================================================================

output "db_instance_id" {
  description = "The RDS instance identifier. Used for AWS CLI commands, monitoring, and resource references."
  value       = aws_db_instance.main.id
}

output "db_instance_arn" {
  description = "The ARN of the RDS instance. Used for IAM policies, CloudWatch alarms, and resource tagging."
  value       = aws_db_instance.main.arn
}

output "db_instance_status" {
  description = "The current status of the RDS instance (e.g., available, backing-up, creating, maintenance)."
  value       = aws_db_instance.main.status
}

# ============================================================================
# Connection Information
# ============================================================================

output "db_endpoint" {
  description = "The connection endpoint in format 'address:port' (e.g., 'mydb.abc123.us-east-2.rds.amazonaws.com:5432'). Use this for direct database connections."
  value       = aws_db_instance.main.endpoint
}

output "db_address" {
  description = "The hostname of the RDS instance (without port). Use this for applications that configure host and port separately."
  value       = aws_db_instance.main.address
}

output "db_port" {
  description = "The port on which the database accepts connections. Default is 5432 for PostgreSQL."
  value       = aws_db_instance.main.port
}

output "db_name" {
  description = "The name of the default database created on the RDS instance. Applications should connect to this database."
  value       = aws_db_instance.main.db_name
}

output "db_username" {
  description = "The master username for the database. Note: Actual password is stored in Secrets Manager, not exposed here."
  value       = aws_db_instance.main.username
  sensitive   = true
}

# ============================================================================
# Secrets Manager Outputs
# ============================================================================

# output "db_secret_arn" {
#   description = "The ARN of the AWS Secrets Manager secret containing database credentials. Applications should use this to retrieve connection details securely."
#   value       = aws_secretsmanager_secret.db_credentials.arn
# }

# output "db_secret_name" {
#   description = "The name/ID of the Secrets Manager secret (e.g., 'drive-ops/dev/rds/credentials'). Use this with AWS SDK to retrieve credentials."
#   value       = aws_secretsmanager_secret.db_credentials.name
# }

# output "db_secret_version_id" {
#   description = "The unique version identifier of the current secret value. Changes when credentials are rotated."
#   value       = aws_secretsmanager_secret_version.db_credentials.version_id
#}

# ============================================================================
# Network Configuration Outputs
# ============================================================================

output "db_subnet_group_name" {
  description = "The name of the DB subnet group. Shows which subnets the RDS instance is deployed in."
  value       = aws_db_subnet_group.main.name
}

output "db_subnet_group_arn" {
  description = "The ARN of the DB subnet group. Used for resource tracking and IAM policies."
  value       = aws_db_subnet_group.main.arn
}

output "db_security_group_ids" {
  description = "List of security group IDs attached to the RDS instance. Should only contain sg-db for restricted access."
  value       = aws_db_instance.main.vpc_security_group_ids
}

# ============================================================================
# Backup and Maintenance Outputs
# ============================================================================

output "db_backup_retention_period" {
  description = "The number of days automated backups are retained. Critical for disaster recovery planning."
  value       = aws_db_instance.main.backup_retention_period
}

output "db_backup_window" {
  description = "The daily time range during which automated backups are created (UTC). Plan maintenance windows around this."
  value       = aws_db_instance.main.backup_window
}

output "db_maintenance_window" {
  description = "The weekly time range during which system maintenance can occur (UTC). Expect brief downtime during this window."
  value       = aws_db_instance.main.maintenance_window
}

output "db_latest_restorable_time" {
  description = "The latest time to which a database can be restored with point-in-time restore (PITR). Used for disaster recovery."
  value       = aws_db_instance.main.latest_restorable_time
}

# ============================================================================
# High Availability and Performance Outputs
# ============================================================================

output "db_multi_az" {
  description = "Indicates if the RDS instance is deployed across multiple availability zones for high availability."
  value       = aws_db_instance.main.multi_az
}

output "db_availability_zone" {
  description = "The availability zone where the primary RDS instance is deployed. For Multi-AZ, standby is in a different AZ."
  value       = aws_db_instance.main.availability_zone
}

output "db_storage_encrypted" {
  description = "Indicates whether the RDS instance storage is encrypted at rest. Should always be true for security compliance."
  value       = aws_db_instance.main.storage_encrypted
}

output "db_performance_insights_enabled" {
  description = "Indicates if Performance Insights is enabled for advanced monitoring and troubleshooting."
  value       = aws_db_instance.main.performance_insights_enabled
}

# ============================================================================
# Resource Tags
# ============================================================================

output "db_tags" {
  description = "The tags assigned to the RDS instance. Used for cost allocation, automation, and compliance tracking."
  value       = aws_db_instance.main.tags_all
}

# ============================================================================
# Convenience Outputs for Applications
# ============================================================================

output "connection_string" {
  description = "PostgreSQL connection string format. Note: Does not include password - retrieve from Secrets Manager. Format: postgresql://username@host:port/dbname"
  value       = "postgresql://${aws_db_instance.main.username}@${aws_db_instance.main.address}:${aws_db_instance.main.port}/${aws_db_instance.main.db_name}"
  sensitive   = true
}

output "db_connection_info" {
  description = "Consolidated connection information object for easy reference. Password must be retrieved separately from Secrets Manager."
  value = {
    host              = aws_db_instance.main.address
    port              = aws_db_instance.main.port
    database          = aws_db_instance.main.db_name
    username          = aws_db_instance.main.username
    # secret_arn          = aws_secretsmanager_secret.db_credentials.arn
    # secret_name         = aws_secretsmanager_secret.db_credentials.name
    endpoint          = aws_db_instance.main.endpoint
    availability_zone = aws_db_instance.main.availability_zone
    multi_az          = aws_db_instance.main.multi_az
    storage_encrypted = aws_db_instance.main.storage_encrypted
  }
}

# ============================================================================
# Password Output (DISABLED BY DEFAULT - Security Risk)
# ============================================================================
#
# SECURITY WARNING: This output is disabled by default to prevent credential leakage.
#
# WHY IS THIS DISABLED?
# - Terraform outputs can leak through CI/CD logs
# - State files (even in S3) are not suitable for storing passwords
# - Console output may be captured in screenshots or logs
# - Violates principle of least privilege
#
# HOW TO ACCESS THE PASSWORD:
# - For applications: Use AWS Secrets Manager (when implemented)
# - For local debugging: Set variable expose_master_password = true (NEVER in production!)
# - For emergency access: Use AWS Console to reset the RDS password
#
# TO ENABLE THIS OUTPUT (LOCAL DEBUGGING ONLY):
# In your terragrunt.hcl or terraform.tfvars:
#   expose_master_password = true
#
# ============================================================================

output "db_master_password" {
  description = "The master password for the database. DISABLED BY DEFAULT for security. Only exposed when var.expose_master_password = true. Applications must retrieve passwords from Secrets Manager, not from Terraform outputs."
  value       = var.expose_master_password ? random_password.master_password.result : null
  sensitive   = true

  # Add precondition to warn users
  precondition {
    condition     = var.expose_master_password == false || var.env != "prod"
    error_message = "SECURITY ERROR: Cannot expose master password in production environment (env=prod). Use AWS Secrets Manager instead."
  }
}
