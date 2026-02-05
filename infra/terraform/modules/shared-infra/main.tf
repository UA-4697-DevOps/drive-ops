# terraform/modules/shared-infra/main.tf
# Composition module that combines VPC and SQS

module "vpc" {
  source = "../vpc"

  project_name       = var.project_name
  env                = var.env
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
}

module "sqs_messaging" {
  source = "../sqs-messaging"

  project_name = var.project_name
  env          = var.env
  cost_center  = var.cost_center
  enable_ha    = var.enable_ha

  message_retention = var.message_retention
  max_receive_count = var.max_receive_count

  trip_created_visibility_timeout    = var.trip_created_visibility_timeout
  driver_assigned_visibility_timeout = var.driver_assigned_visibility_timeout
  trip_completed_visibility_timeout  = var.trip_completed_visibility_timeout

  common_tags = var.common_tags
}
