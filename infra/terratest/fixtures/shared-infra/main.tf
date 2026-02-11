provider "aws" {
  region                      = "us-east-2"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  access_key = "mock_access_key"
  secret_key = "mock_secret_key"
}

module "shared_infra" {
  # Path to your actual infrastructure module
  source = "../../../terraform/modules/shared-infra"

  # Pass ALL variables required by the module here
  project_name                       = var.project_name
  env                                = var.env
  account_id                         = var.account_id
  cost_center                        = var.cost_center
  vpc_cidr                           = var.vpc_cidr
  availability_zones                 = var.availability_zones
  enable_flow_logs                   = var.enable_flow_logs
  flow_log_retention_in_days         = var.flow_log_retention_in_days
  enable_ha                          = var.enable_ha
  message_retention                  = var.message_retention
  max_receive_count                  = var.max_receive_count
  trip_created_visibility_timeout    = var.trip_created_visibility_timeout
  driver_assigned_visibility_timeout = var.driver_assigned_visibility_timeout
  trip_completed_visibility_timeout  = var.trip_completed_visibility_timeout
  common_tags                        = var.common_tags
}

# Variable declarations to pass data into the fixture
variable "project_name" {}
variable "env" {}
variable "account_id" {}
variable "cost_center" {}
variable "vpc_cidr" {}
variable "availability_zones" { type = list(string) }
variable "enable_flow_logs" { type = bool }
variable "flow_log_retention_in_days" { type = number }
variable "enable_ha" { type = bool }
variable "message_retention" { type = number }
variable "max_receive_count" { type = number }
variable "trip_created_visibility_timeout" { type = number }
variable "driver_assigned_visibility_timeout" { type = number }
variable "trip_completed_visibility_timeout" { type = number }
variable "common_tags" { type = map(string) }
