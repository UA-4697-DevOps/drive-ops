# ==============================================================================
# BASTION HOST – TERRAGRUNT STACK (DEV)
# ==============================================================================
# Deploys a hardened SSH jump-host in a public subnet.
# SSH access is restricted to the CIDRs listed in BASTION_ALLOWED_SSH_CIDRS.
#
# VPN access is managed by the separate envs/dev/vpn/ stack.
#
# Dependencies:
#   shared-infra → VPC, public subnets
#
# Usage:
#   cd infra/terragrunt/envs/dev/bastion
#   terragrunt plan
#   terragrunt apply
#
# Connect via SSH:
#   ssh -i ~/.ssh/<key>.pem ec2-user@$(terragrunt output -raw bastion_public_ip)
#
# Connect via SSM Session Manager (no SSH key required):
#   aws ssm start-session --target $(terragrunt output -raw bastion_instance_id)
# ==============================================================================

include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform//modules/bastion"
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

dependency "shared_infra" {
  config_path = "../shared-infra"

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
  mock_outputs_merge_strategy_with_state  = "shallow"

  mock_outputs = {
    vpc_id            = "vpc-mock-id"
    vpc_cidr          = "10.0.0.0/16"
    public_subnet_ids = ["subnet-mock-pub-1", "subnet-mock-pub-2"]
  }
}

inputs = {
  project_name = local.common_vars.project_name
  env          = local.env_vars.env
  account_id   = local.env_vars.account_id

  vpc_id           = dependency.shared_infra.outputs.vpc_id
  vpc_cidr_block   = dependency.shared_infra.outputs.vpc_cidr
  public_subnet_id = try(dependency.shared_infra.outputs.public_subnet_ids[0], "")

  # t4g.nano: ARM/Graviton — cheapest option, sufficient for SSH jump-host
  instance_type = "t4g.nano"

  # EC2 Key Pair that MUST already exist in AWS (create manually or via CLI)
  key_name = "bastion-key"

  # Source IP allowlist — injected exclusively from the GitHub Actions secret
  # TG_VAR_BASTION_ALLOWED_SSH_CIDRS (e.g. '["203.0.113.10/32"]').
  # Fails with a Terragrunt error if the env var is absent — no insecure fallback.
  allowed_ssh_cidrs = jsondecode(get_env("TG_VAR_BASTION_ALLOWED_SSH_CIDRS"))

  tags = {
    Component = "bastion"
  }
}
