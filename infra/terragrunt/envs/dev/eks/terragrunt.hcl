# ==============================================================================
# EKS TERRAGRUNT STACK – DEV ENVIRONMENT
# ==============================================================================
# Deploys a managed EKS cluster into the existing VPC created by shared-infra.
#
# Dependencies:
#   shared-infra → VPC, subnets, security groups
#
# Usage:
#   cd infra/terragrunt/envs/dev/eks
#   terragrunt plan
#   terragrunt apply
#
# Post-apply:
#   Run the kubeconfig_command output to configure kubectl:
#   $(terragrunt output -raw kubeconfig_command)
# ==============================================================================

include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform//modules/eks"
}

# --- Load Common & Env Variables ---

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

# --- Dependencies ---

dependency "shared_infra" {
  config_path = "../shared-infra"

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init", "destroy"]
  mock_outputs_merge_strategy_with_state  = "shallow"

  mock_outputs = {
    vpc_id             = "vpc-mock-id"
    public_subnet_ids  = ["subnet-mock-pub-1", "subnet-mock-pub-2"]
    private_subnet_ids = ["subnet-mock-priv-1", "subnet-mock-priv-2"]
  }
}

# --- Inputs ---

inputs = {
  # Global
  project_name = local.common_vars.project_name
  env          = local.env_vars.env
  account_id   = local.env_vars.account_id

  # Networking (from shared-infra)
  vpc_id             = dependency.shared_infra.outputs.vpc_id
  private_subnet_ids = dependency.shared_infra.outputs.private_subnet_ids
  public_subnet_ids  = dependency.shared_infra.outputs.public_subnet_ids

  # Cluster
  cluster_version                        = "1.35"
  cluster_endpoint_public_access         = true
  cluster_endpoint_private_access        = true
  cluster_endpoint_public_access_cidrs   = ["0.0.0.0/0"] # TODO: restrict to bastion/VPN CIDRs after next task
  enabled_cluster_log_types              = ["audit", "api", "authenticator"]
  cluster_log_retention_in_days          = 7

  # Node Group
  node_instance_types = ["t3.small"]
  node_desired_size   = 2
  node_min_size       = 2
  node_max_size       = 4
  node_disk_size      = 20
  node_capacity_type  = "ON_DEMAND"
  # Place nodes in public subnets and assign public IPs so they can reach the
  # EKS control plane and AWS APIs without a NAT gateway (NATless VPC design).
  node_subnet_ids                 = dependency.shared_infra.outputs.public_subnet_ids
  node_associate_public_ip_address = true

  tags = {
    Component = "eks"
  }
}
