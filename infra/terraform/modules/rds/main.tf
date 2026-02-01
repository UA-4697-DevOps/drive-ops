resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.env}-db-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "${var.project_name}-${var.env}-db-subnet-group"
  }
}

locals {
  # Generate a default final snapshot identifier when needed
  # Format: project-env-postgres-final-YYYYMMDDHHMMSS
  default_snapshot_id = "${var.project_name}-${var.env}-postgres-final-${formatdate("YYYYMMDDhhmmss", timestamp())}"

  # Use provided snapshot ID if given, otherwise use generated default
  final_snapshot_id = var.final_snapshot_identifier != "" ? var.final_snapshot_identifier : local.default_snapshot_id
}

resource "aws_db_instance" "main" {
  identifier = "${var.project_name}-${var.env}-postgres"

  engine         = var.engine
  engine_version = var.engine_version

  instance_class    = var.instance_class
  allocated_storage = var.allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.master_username
  password = var.master_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.db_security_group_id]
  publicly_accessible    = false

  backup_retention_period   = var.backup_retention_period
  multi_az                  = var.multi_az
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : local.final_snapshot_id

  # Performance Insights (CKV_AWS_354 compliance)
  performance_insights_enabled          = var.enable_performance_insights
  performance_insights_retention_period = var.enable_performance_insights ? var.performance_insights_retention_period : null
  performance_insights_kms_key_id       = var.enable_performance_insights ? var.performance_insights_kms_key_id : null

  tags = var.tags

  # Validation: Performance Insights requires customer-managed KMS key
  lifecycle {
    precondition {
      condition     = !var.enable_performance_insights || var.performance_insights_kms_key_id != null
      error_message = "SECURITY REQUIREMENT (CKV_AWS_354): When enable_performance_insights is true, performance_insights_kms_key_id must be provided with a customer-managed KMS key ARN. Performance Insights data must be encrypted with a CMK for compliance."
    }
  }
}
