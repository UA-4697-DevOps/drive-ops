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

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
  mock_outputs_merge_strategy_with_state  = "shallow"

  mock_outputs = {
    vpc_id             = "vpc-mock-id"
    public_subnet_ids  = ["subnet-mock-pub-1", "subnet-mock-pub-2"]
    private_subnet_ids = ["subnet-mock-priv-1", "subnet-mock-priv-2"]
    kms_key_arn        = "arn:aws:kms:us-east-2:123456789012:key/mock-key-id"
  }
}

dependency "bastion" {
  config_path = "../bastion"

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
  mock_outputs_merge_strategy_with_state  = "shallow"

  mock_outputs = {
    bastion_security_group_id = "sg-mock-bastion"
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
  cluster_version                        = "1.35"  # cgroup v2 properly configured via AL2023_x86_64_STANDARD AMI (default)
  cluster_endpoint_public_access         = false  # API only reachable from within VPC (bastion / OpenVPN)
  cluster_endpoint_private_access        = true
  enabled_cluster_log_types              = ["audit", "api", "authenticator"]
  cluster_log_retention_in_days          = 7

  # Node Group
  node_instance_types = ["t3.medium"]
  node_desired_size   = 2
  node_min_size       = 2
  node_max_size       = 4
  node_disk_size      = 50
  node_capacity_type  = "ON_DEMAND"
  # Nodes in private subnets — outbound traffic goes via NAT Instance.
  # node_subnet_ids defaults to private_subnet_ids inside the EKS module,
  # so no explicit override is needed.
  node_associate_public_ip_address = false

  # Allow bastion → node SSH for debugging (port 22 ingress on node SG).
  # Engineers can also use SSM Session Manager without this rule.
  bastion_sg_id = dependency.bastion.outputs.bastion_security_group_id

  # Customer-managed KMS key for encrypting EKS secrets and CloudWatch Logs
  kms_key_arn = dependency.shared_infra.outputs.kms_key_arn

  tags = {
    Component = "eks"
  }
}
