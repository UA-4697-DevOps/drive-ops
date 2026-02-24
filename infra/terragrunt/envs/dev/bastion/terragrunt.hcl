# ==============================================================================
# BASTION HOST – TERRAGRUNT STACK (DEV)
# ==============================================================================
# Deploys a hardened bastion EC2 instance in a public subnet.
# SSH access is restricted to the CIDRs listed in allowed_ssh_cidrs.
#
# Dependencies:
#   shared-infra → VPC, public subnets
#
# Usage:
#   cd infra/terragrunt/envs/dev/bastion
#   terragrunt plan
#   terragrunt apply
#
# Connect:
#   ssh -i ~/.ssh/<key>.pem ec2-user@$(terragrunt output -raw bastion_public_ip)
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
  # Whether to enable OpenVPN on the bastion. Prefer explicit setting in env_vars.yaml,
  # otherwise default to true for this dev stack.
  openvpn_enabled = coalesce(local.env_vars.enable_openvpn, true)
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

  vpc_id           = dependency.shared_infra.outputs.vpc_id
  # Validate public_subnet_ids length before accessing the first element
  public_subnet_id = length(dependency.shared_infra.outputs.public_subnet_ids) > 0 ? dependency.shared_infra.outputs.public_subnet_ids[0] : (throw("No public subnets found in shared_infra output"))

  # Instance type: choose a larger instance when OpenVPN is enabled
  instance_type = local.openvpn_enabled ? "t4g.micro" : "t4g.nano"

  # EC2 Key Pair that MUST already exist in AWS (create manually or via CLI)
  key_name = "bastion-key"

  # STRICT IP ALLOWLIST — managed in env_vars.yaml (key: BASTION_ALLOWED_SSH_CIDRS)
  # Override via environment variable: TG_VAR_BASTION_ALLOWED_SSH_CIDRS='["YOUR_IP/32"]'
  allowed_ssh_cidrs = length(get_env("TG_VAR_BASTION_ALLOWED_SSH_CIDRS", "")) > 0 ? jsondecode(get_env("TG_VAR_BASTION_ALLOWED_SSH_CIDRS")) : local.env_vars.BASTION_ALLOWED_SSH_CIDRS

  # OpenVPN server for secure administrative VPN access to private resources
  enable_openvpn = local.openvpn_enabled
  vpc_cidr       = dependency.shared_infra.outputs.vpc_cidr

  tags = {
    Component = "bastion"
  }
}
