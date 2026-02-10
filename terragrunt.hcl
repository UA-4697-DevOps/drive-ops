include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules//vpc"
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

inputs = {
  project_name = local.common_vars.project_name
  env          = "dev"
  cost_center  = local.common_vars.cost_center
  
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["us-east-2a", "us-east-2b"]
  
  enable_ha         = false
  message_retention = 345600
  max_receive_count = 3
  
  trip_created_visibility_timeout    = 60
  driver_assigned_visibility_timeout = 60
  trip_completed_visibility_timeout  = 60

  common_tags = {
    Module      = "shared-infra"
    Owner       = "DevOps Team"
    Description = "Shared infrastructure for drive-ops VPC and SQS"
  }
}
