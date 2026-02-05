# Root Terragrunt configuration
# This file contains shared configuration for all environments

locals {
  # Load common variables shared across all environments
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))

  # Load environment-specific variables
  env_vars = yamldecode(file(find_in_parent_folders("env_vars.yaml")))

  # Extract commonly used values
  project_name = local.common_vars.project_name
  env          = local.env_vars.env
  aws_region   = try(local.env_vars.aws_region, local.common_vars.aws_region)

  # NEW: "Feed" the account ID from an environment variable
  aws_account_id = get_env("AWS_ACCOUNT_ID")

  # Merge common and environment-specific tags
  tags = merge(
    local.common_vars.common_tags,
    local.env_vars.env_tags
  )

  # Check if current path is in "envs/local" directory (for local testing)
  # If true, skip S3 backend generation and use local state instead
  is_local_env = can(regex(".*/envs/local/.*", get_terragrunt_dir()))
}

# Configure remote state backend
# Note: Skipped for modules in "local/" directory - they use local state
# All other modules will use S3 backend
generate "backend" {
  path      = "backend.tf"
  if_exists = "overwrite_terragrunt"
  contents  = local.is_local_env ? "" : <<EOF
terraform {
  backend "s3" {
    bucket         = "${local.project_name}-${local.env}-terraform-state"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = "${local.aws_region}"
    encrypt        = true
    dynamodb_table = "${local.project_name}-${local.env}-terraform-locks"
  }
}
EOF
}

# Generate provider configuration
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = "${local.aws_region}"

  default_tags {
    tags = ${jsonencode(local.tags)}
  }
}
EOF
}

# Common inputs to pass to all Terraform modules
inputs = {
  project_name = local.project_name
  env          = local.env
  aws_region   = local.aws_region
  account_id   = local.aws_account_id
  tags         = local.tags
  enable_ha    = try(local.env_vars.enable_ha, false)
  cost_center  = local.common_vars.cost_center
  owner        = local.common_vars.owner
}
