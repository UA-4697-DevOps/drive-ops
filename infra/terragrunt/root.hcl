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

  # Merge common and environment-specific tags
  tags = merge(
    local.common_vars.common_tags,
    local.env_vars.env_tags
  )
}

# Configure remote state backend
# Note: For the state-backend module itself, this will be skipped
# All other modules will use this configuration
generate "backend" {
  path      = "backend.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
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
  tags         = local.tags
  enable_ha    = try(local.env_vars.enable_ha, false)
  cost_center  = local.common_vars.cost_center
  owner        = local.common_vars.owner
}
