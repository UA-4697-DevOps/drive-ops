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

# --- Infrastructure Dependencies ---

dependency "shared_infra" {
  config_path = "../shared-infra"

  # Allows planning even if shared-infra outputs are not yet available in the state
  # Removed "apply" to enforce using real outputs during deployment
  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init", "destroy"]
  mock_outputs = {
    sqs_names = {
      trip_created = "mock-trip-created"
    }
    # Secure ARN mock for the Discord webhook secret
    discord_secret_arn = "arn:aws:secretsmanager:us-east-2:123456789012:secret:mock-discord"
  }
}

dependency "rds" {
  config_path                             = "../rds"
  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init", "destroy"]
  mock_outputs = {
    db_instance_id = "mock-db-id"
  }
}

# --- Compute Dependencies ---

dependency "client_gateway" {
  config_path                             = "../client-gateway"
  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init", "destroy"]
  mock_outputs                            = { instance_id = "i-mock-client-gateway" }
}

dependency "driver_service" {
  config_path                             = "../driver-service"
  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init", "destroy"]
  mock_outputs                            = { instance_id = "i-mock-driver-service" }
}

dependency "trip_service" {
  config_path                             = "../trip-service"
  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init", "destroy"]
  mock_outputs                            = { instance_id = "i-mock-trip-service" }
}

# --- Inputs ---

inputs = {
  # General Project Variables
  project_name = local.common_vars.project_name
  env          = local.env_vars.env
  account_id   = local.env_vars.account_id

  # List of services for centralized log group creation
  service_names = ["client-gateway", "driver-service", "trip-service"]

  # Dynamic resource IDs fetched from dependencies
  rds_instance_id = dependency.rds.outputs.db_instance_id
  sqs_queue_name  = dependency.shared_infra.outputs.sqs_names["trip_created"]

  # Mapping service names to their specific EC2 Instance IDs for CloudWatch Alarms
  ec2_instances = {
    "client-gateway" = dependency.client_gateway.outputs.instance_id
    "driver-service" = dependency.driver_service.outputs.instance_id
    "trip-service"   = dependency.trip_service.outputs.instance_id
  }

  # SECURITY FIX: Pass the Secret ARN instead of the raw URL environment variable.
  # This enables runtime secret retrieval and prevents plaintext leaks in the state file.
  discord_webhook_secret_arn = dependency.shared_infra.outputs.discord_secret_arn
}
