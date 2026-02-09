# terraform/modules/shared-infra/main.tf
module "vpc" {
  source = "../vpc"

  project_name       = var.project_name
  env                = var.env
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
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
