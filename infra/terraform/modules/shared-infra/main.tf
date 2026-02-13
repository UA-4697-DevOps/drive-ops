# terraform/modules/shared-infra/main.tf
module "vpc" {
  source = "../vpc"

  project_name               = var.project_name
  account_id                 = var.account_id
  env                        = var.env
  vpc_cidr                   = var.vpc_cidr
  availability_zones         = var.availability_zones
  enable_flow_logs           = var.enable_flow_logs
  flow_log_retention_in_days = var.flow_log_retention_in_days
}

# Trip Created Queue
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

# Driver Assigned Queue
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

# Trip Completed Queue
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

# --- ECR Repositories ---

# ECR for Client Gateway (Python)
module "ecr_client_gateway" {
  source = "../ecr"

  repository_name = "client-gateway"
  account_id      = var.account_id
  github_repo     = var.github_repo
}

# ECR for Driver Service (Python)
module "ecr_driver_service" {
  source = "../ecr"

  repository_name = "driver-service"
  account_id      = var.account_id
  github_repo     = var.github_repo
}

# ECR for Trip Service (Go)
module "ecr_trip_service" {
  source = "../ecr"

  repository_name = "trip-service"
  account_id      = var.account_id
  github_repo     = var.github_repo
}

# --- RDS Secrets ---

module "rds_secrets" {
  source = "../secrets"

  project_name        = var.project_name
  env                 = var.env
  db_identifier       = var.db_identifier
  rds_master_username = var.rds_master_username

  tags = merge(var.common_tags, {
    Component = "secrets-manager"
  })
}
