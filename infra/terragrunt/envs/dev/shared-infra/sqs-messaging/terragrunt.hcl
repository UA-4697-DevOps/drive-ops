+# envs/dev/shared-infra/sqs-messaging/terragrunt.hcl

include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../../terraform/modules//sqs-messaging"
}

# Load common variables
locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

inputs = {
  # Global variables from common_vars.yaml
  project_name = local.common_vars.project_name
  env          = "dev"
  cost_center  = local.common_vars.cost_center
  
  # High Availability (disabled for dev)
  enable_ha = false

  # Common queue settings
  message_retention = 345600  # 4 days
  max_receive_count = 3

  # Per-queue visibility timeouts
  trip_created_visibility_timeout     = 60
  driver_assigned_visibility_timeout  = 60
  trip_completed_visibility_timeout   = 60

  # Common tags for all queues
  common_tags = {
    Module      = "sqs-messaging"
    Owner       = "DevOps Team"
    Description = "SQS messaging infrastructure for drive-ops"
  }
}
