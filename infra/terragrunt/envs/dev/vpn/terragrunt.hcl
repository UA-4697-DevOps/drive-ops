# ==============================================================================
# VPN (OpenVPN) – TERRAGRUNT STACK (DEV)
# ==============================================================================
# Deploys a standalone OpenVPN server on a dedicated Graviton EC2 instance in
# the public subnet. Provides secure administrative VPN access to private
# VPC resources (EKS worker nodes, RDS, etc.) without exposing them directly.
#
# Architecture:
#   - Separate EC2 from the SSH bastion (distinct concerns, distinct instances)
#   - AL2023 ARM64 (t4g.micro — Graviton AES-256-GCM hardware acceleration)
#   - PKI persisted to Secrets Manager (survives instance replacement)
#   - Client .ovpn profile stored in Secrets Manager (KMS-encrypted)
#
# Retrieve client config after apply:
#   aws secretsmanager get-secret-value \
#     --secret-id "<project>/<env>/openvpn/clients/client1" \
#     --region us-east-2 --query SecretString --output text > client1.ovpn
#
# Dependencies:
#   shared-infra → VPC, public subnets, KMS key
#
# Usage:
#   terragrunt plan
#   terragrunt apply
# ==============================================================================

include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform//modules/vpn"
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
    kms_key_arn       = "arn:aws:kms:us-east-2:123456789012:key/mock-key-id"
  }
}

inputs = {
  project_name = local.common_vars.project_name
  env          = local.env_vars.env
  account_id   = local.env_vars.account_id
  aws_region   = local.common_vars.aws_region

  vpc_id           = dependency.shared_infra.outputs.vpc_id
  vpc_cidr         = dependency.shared_infra.outputs.vpc_cidr
  public_subnet_id = try(dependency.shared_infra.outputs.public_subnet_ids[0], "")

  # t4g.micro: ARM/Graviton — hardware-accelerated AES-256-GCM for OpenVPN
  instance_type = "t4g.micro"

  # VPN client tunnel network (must not overlap with vpc_cidr = 10.0.0.0/16)
  vpn_client_cidr = "10.8.0.0/24"

  # Source IP allowlist — injected exclusively from the GitHub Actions secret
  # TG_VAR_BASTION_ALLOWED_SSH_CIDRS (e.g. '["203.0.113.10/32"]').
  # Fails with a Terragrunt error if the env var is absent — no insecure fallback.
  allowed_vpn_cidrs = jsondecode(get_env("TG_VAR_BASTION_ALLOWED_SSH_CIDRS"))

  # Use the default aws/secretsmanager KMS key (free) instead of the CMK.
  # Set to dependency.shared_infra.outputs.kms_key_arn to use the customer-managed key.
  kms_key_arn = null

  tags = {
    Component = "vpn"
  }
}
