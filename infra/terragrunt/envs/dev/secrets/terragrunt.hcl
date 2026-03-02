# ==============================================================================
# SECRETS MANAGER – TERRAGRUNT STACK (DEV)
# ==============================================================================
# Manages RDS master password and other sensitive credentials in AWS Secrets Manager.
#
# Dependencies:
#   shared-infra → KMS key for encryption
#
# Usage:
#   cd infra/terragrunt/envs/dev/secrets
#   terragrunt plan
#   terragrunt apply
# ==============================================================================

include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform//modules/secrets"
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

inputs = {
  project_name = local.common_vars.project_name
  env          = local.env_vars.env

  # RDS Secrets Configuration
  db_identifier       = "Training-${local.common_vars.project_name}-${local.env_vars.env}-db"
  rds_master_username = "drive_admin"

  # Discord webhook URL for alerts (set via environment variable or console)
  discord_webhook_url = get_env("TF_VAR_discord_webhook_url", "https://discord.com/api/webhooks/PLACEHOLDER")

  tags = {
    Component = "secrets-manager"
  }
}
