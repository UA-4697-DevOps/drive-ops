# ------------------------------------------------------------------------------
# SHARED INFRASTRUCTURE MODULE
# ------------------------------------------------------------------------------
# This module creates the foundational resources shared across the environment:
# 1. Networking (VPC)
# 2. Event Bus (SQS Queues)
# 3. Artifact Registry (ECR)
# 4. Security & Secrets (Secrets Manager)
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# 1. NETWORKING
# ------------------------------------------------------------------------------
module "vpc" {
  source = "../vpc"

  project_name = var.project_name
  account_id   = var.account_id
  env          = var.env

  vpc_cidr                      = var.vpc_cidr
  availability_zones            = var.availability_zones
  enable_flow_logs              = var.enable_flow_logs
  flow_log_retention_in_days    = var.flow_log_retention_in_days
  use_nat_instance              = var.use_nat_instance
  nat_instance_type             = var.nat_instance_type
  nat_instance_key_name         = var.nat_instance_key_name
  nat_bastion_allowed_ssh_cidrs = var.nat_bastion_allowed_ssh_cidrs
}

# ------------------------------------------------------------------------------
# 2. EVENT BUS (SQS)
# ------------------------------------------------------------------------------

# Queue: Trip Created (Producers: Trip Service | Consumers: Driver Service)
module "trip_created" {
  source = "../sqs"

  project_name = var.project_name
  env          = var.env
  cost_center  = var.cost_center
  enable_ha    = var.enable_ha

  queue_name         = "trip-created"
  visibility_timeout = var.trip_created_visibility_timeout
  message_retention  = var.message_retention
  max_receive_count  = var.max_receive_count

  tags = merge(var.common_tags, {
    Component = "sqs-trip-created"
    Queue     = "trip.created"
    EventType = "trip.event.created"
  })
}

# Queue: Driver Assigned (Producers: Driver Service | Consumers: Client Gateway)
module "driver_assigned" {
  source = "../sqs"

  project_name = var.project_name
  env          = var.env
  cost_center  = var.cost_center
  enable_ha    = var.enable_ha

  queue_name         = "driver-assigned"
  visibility_timeout = var.driver_assigned_visibility_timeout
  message_retention  = var.message_retention
  max_receive_count  = var.max_receive_count

  tags = merge(var.common_tags, {
    Component = "sqs-driver-assigned"
    Queue     = "driver.assigned"
    EventType = "trip.event.driver_assigned"
  })
}

# Queue: Trip Completed (Producers: Driver Service | Consumers: Billing/Analytics)
module "trip_completed" {
  source = "../sqs"

  project_name = var.project_name
  env          = var.env
  cost_center  = var.cost_center
  enable_ha    = var.enable_ha

  queue_name         = "trip-completed"
  visibility_timeout = var.trip_completed_visibility_timeout
  message_retention  = var.message_retention
  max_receive_count  = var.max_receive_count

  tags = merge(var.common_tags, {
    Component = "sqs-trip-completed"
    Queue     = "trip.completed"
    EventType = "trip.event.completed"
  })
}

# ------------------------------------------------------------------------------
# 3. ARTIFACT REGISTRY (ECR)
# ------------------------------------------------------------------------------

module "ecr_client_gateway" {
  source = "../ecr"

  repository_name = "client-gateway"
  account_id      = var.account_id
  github_repo     = var.github_repo
}

module "ecr_driver_service" {
  source = "../ecr"

  repository_name = "driver-service"
  account_id      = var.account_id
  github_repo     = var.github_repo
}

module "ecr_trip_service" {
  source = "../ecr"

  repository_name = "trip-service"
  account_id      = var.account_id
  github_repo     = var.github_repo
}

# ------------------------------------------------------------------------------
# 4. ENCRYPTION (KMS)
# ------------------------------------------------------------------------------

# Customer-managed KMS key for encrypting sensitive data:
# - EKS cluster secrets (envelope encryption)
# - CloudWatch Logs for EKS and other services
# - RDS Performance Insights (when enabled)
resource "aws_kms_key" "cmk" {
  description             = "Customer-managed KMS key for ${var.project_name}-${var.env} encryption (EKS, CloudWatch, RDS)"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags = merge(var.common_tags, {
    Name = "${var.project_name}-${var.env}-cmk"
  })
}

resource "aws_kms_alias" "cmk" {
  name          = "alias/${var.project_name}-${var.env}-encryption"
  target_key_id = aws_kms_key.cmk.key_id
}

# ------------------------------------------------------------------------------
# 5. SECURITY & SECRETS
# ------------------------------------------------------------------------------

module "rds_secrets" {
  source = "../secrets"

  project_name        = var.project_name
  env                 = var.env
  db_identifier       = var.db_identifier
  rds_master_username = var.rds_master_username
  discord_webhook_url = var.discord_webhook_url

  tags = merge(var.common_tags, {
    Component = "secrets-manager"
  })
}
