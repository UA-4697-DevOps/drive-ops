# State backend module configuration for dev environment
# This module creates the S3 bucket and DynamoDB table for remote state

# Include root configuration
include "root" {
  path = find_in_parent_folders()
}

# Point to the Terraform module
terraform {
  source = "../../../../terraform/modules/state-backend"
}

# Load local variables
locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))

  project_name = local.common_vars.project_name
  env          = local.env_vars.env
}

# Skip backend generation for this module (chicken-and-egg problem)
# We need to create the state backend resources first before we can use them
skip_backend_generation = true

# Module-specific inputs
inputs = {
  state_bucket_name = "${local.project_name}-${local.env}-terraform-state"
  lock_table_name   = "${local.project_name}-${local.env}-terraform-locks"
}
