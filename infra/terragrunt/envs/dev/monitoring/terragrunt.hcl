include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform//modules/monitoring"
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

dependency "shared_infra" {
  config_path = "../shared-infra"

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init", "destroy"]
  mock_outputs = {
    sqs_names = {
      trip_created = "mock-trip-created"
    }
  }
}

dependency "rds" {
  config_path = "../rds"

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init", "destroy"]
  mock_outputs = {
    db_instance_id = "mock-db-id"
  }
}

#dependency "compute" {
#  config_path = "../compute" 
#  
#  mock_outputs = {
#    cluster_name = "mock-cluster"
#  }
#}

inputs = {
  # General Project Variables (matching VPC module)
  project_name = local.common_vars.project_name
  env          = local.env_vars.env
  account_id   = local.env_vars.account_id

  # Monitoring Specifics
  service_names = ["client-gateway", "driver-service", "trip-service"]

  # Infrastructure Dependencies
  rds_instance_id  = dependency.rds.outputs.db_instance_id
  sqs_queue_name   = dependency.shared_infra.outputs.sqs_names["trip_created"]
  ecs_cluster_name = "tbd-cluster-name" # Placeholder until compute is ready

  # Secrets
  discord_webhook_url = get_env("DISCORD_WEBHOOK_URL")
}
