# envs/dev/shared-infra/terragrunt.hcl

include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  # Points to the consolidated shared infrastructure module
  source = "../../../../terraform//modules/shared-infra"
}

# Note: project_name, env, account_id, cost_center, and tags are already
# injected as common Terraform variable inputs by root.hcl.

inputs = {
  # VPC settings
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["us-east-2a", "us-east-2b"]

  # VPC Flow Logs
  enable_flow_logs           = true
  flow_log_retention_in_days = 3

  # SQS settings
  message_retention = 345600
  max_receive_count = 3

  trip_created_visibility_timeout    = 60
  driver_assigned_visibility_timeout = 60
  trip_completed_visibility_timeout  = 60

  # --- ECR & CI/CD Configuration ---
  # Required for GitHub Actions OIDC trust policy in the ECR module
  github_repo = "UA-4697-DevOps/drive-ops"

  # --- RDS Secrets Configuration ---
  # These values are required for the secrets module to generate the master password
  db_identifier       = "Training-drive-ops-dev-db"
  rds_master_username = "drive_admin"

  # --- Monitoring & Alerting (Discord) ---
  discord_webhook_url = get_env("TF_VAR_discord_webhook_url", "https://discord.com/api/webhooks/1234567890/dummy_token")

  # --- Client-Gateway Secrets ---
  telegram_bot_token = get_env("TF_VAR_telegram_bot_token")

  # Common tags
  common_tags = {
    Module      = "shared-infra"
    Owner       = "DevOps Team"
    Description = "Shared infrastructure including VPC SQS ECR and Secrets"
  }
}

