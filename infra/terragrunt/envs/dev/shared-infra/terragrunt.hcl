# envs/dev/shared-infra/terragrunt.hcl

include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  # Points to the consolidated shared infrastructure module
  source = "../../../../terraform//modules/shared-infra"
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

inputs = {
  # Global variables
  project_name = local.common_vars.project_name
  env          = local.env_vars.env
  cost_center  = local.common_vars.cost_center
  account_id   = local.env_vars.account_id

  # VPC settings
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["us-east-2a", "us-east-2b"]

  # VPC Flow Logs
  enable_flow_logs           = true
  flow_log_retention_in_days = 3

  # NAT Configuration — NAT Instance (t4g.nano ARM/Graviton) for cost-effective private subnet outbound
  # NAT Instance routes private subnet traffic (0.0.0.0/0) to the Internet Gateway
  # Using fck-nat AMI: production-ready, auto-recovery, CloudWatch monitoring
  # Cost: ~$3/month vs AWS NAT Gateway at ~$32+/month (90% savings)
  #
  # ⚠ SINGLE POINT OF FAILURE (SPOF): A single NAT instance serves both AZs (us-east-2a, us-east-2b).
  #   If the instance or its AZ becomes unavailable, all private-subnet egress is lost.
  #   For production workloads, deploy one NAT instance (or NAT Gateway) per AZ.
  #
  # ⚠ CROSS-AZ DATA CHARGES: Traffic from private subnets in us-east-2b egressing via a NAT
  #   instance in us-east-2a incurs cross-AZ data transfer fees (~$0.01/GB each direction).
  #   At low volumes this is negligible, but it compounds at scale.
  #
  # DEV: Single NAT instance is acceptable for dev/cost savings.
  # PROD: Enable HA by deploying one NAT instance per AZ.
  #   Example (prod):
  #     use_nat_instance  = true
  #     nat_instance_type = "t4g.small"  # Upsize for prod traffic
  #     enable_ha         = true          # Enables one NAT instance per AZ (no SPOF)
  enable_ha          = false            # Controls NAT high-availability (one NAT instance per AZ when true)
  use_nat_instance   = true
  nat_instance_type  = "t4g.nano"  # ARM/Graviton — cheapest option
  # nat_instance_key_name = null  # Optional: set to an EC2 key pair name for SSH break-glass access

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
  db_identifier       = "Training-${local.common_vars.project_name}-${local.env_vars.env}-db"
  rds_master_username = "drive_admin"

  # --- Monitoring & Alerting (Discord) ---
  discord_webhook_url = get_env("TF_VAR_discord_webhook_url")

  # Common tags
  common_tags = {
    Module      = "shared-infra"
    Owner       = "DevOps Team"
    Description = "Shared infrastructure including VPC SQS ECR and Secrets"
  }
}
