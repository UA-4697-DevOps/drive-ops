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
    endpoint          = aws_db_instance.main.endpoint
    availability_zone = aws_db_instance.main.availability_zone
    multi_az          = aws_db_instance.main.multi_az
    storage_encrypted = aws_db_instance.main.storage_encrypted
  }
  sensitive = true
}

# ============================================================================
# Performance Insights Outputs
# ============================================================================

output "performance_insights_enabled" {
  description = "Indicates if Performance Insights is enabled for this RDS instance."
  value       = aws_db_instance.main.performance_insights_enabled
}

output "performance_insights_kms_key_id" {
  description = "The ARN of the KMS key used to encrypt Performance Insights data. Null if Performance Insights is disabled."
  value       = aws_db_instance.main.performance_insights_kms_key_id
}

output "performance_insights_retention_period" {
  description = "The number of days Performance Insights data is retained. Null if Performance Insights is disabled."
  value       = aws_db_instance.main.performance_insights_retention_period
}
