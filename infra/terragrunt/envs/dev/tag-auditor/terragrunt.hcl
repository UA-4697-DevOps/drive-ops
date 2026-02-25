include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules//tag-auditor"
}

# --- Load Common & Env Variables ---
locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

# --- Dependencies ---
dependency "monitoring" {
  config_path = "../monitoring"

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init", "destroy"]
  mock_outputs_merge_strategy_with_state  = "shallow"

  mock_outputs = {
    sns_topic_arn = "arn:aws:sns:us-east-2:000000000000:drive-ops-dev-alerts"
  }
}

dependency "shared_infra" {
  config_path = "../shared-infra"

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init", "destroy"]
  mock_outputs_merge_strategy_with_state  = "shallow"

  mock_outputs = {
    sqs_arns = {
      trip_created    = "arn:aws:sqs:us-east-2:000000000000:trip-created.fifo"
      driver_assigned = "arn:aws:sqs:us-east-2:000000000000:driver-assigned.fifo"
      trip_completed  = "arn:aws:sqs:us-east-2:000000000000:trip-completed.fifo"
    }
  }
}

# --- Inputs ---
inputs = {
  project_name  = local.common_vars.project_name
  env           = local.env_vars.env
  account_id    = local.env_vars.account_id
  sns_topic_arn = dependency.monitoring.outputs.sns_topic_arn
  sqs_queue_arns = [
    dependency.shared_infra.outputs.sqs_arns["trip_created"],
    dependency.shared_infra.outputs.sqs_arns["driver_assigned"],
    dependency.shared_infra.outputs.sqs_arns["trip_completed"],
  ]
}
