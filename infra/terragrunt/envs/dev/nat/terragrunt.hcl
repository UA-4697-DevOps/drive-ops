# ==============================================================================
# NAT INSTANCE – TERRAGRUNT STACK (DEV)
# ==============================================================================
# Deploys a cost-effective fck-nat EC2 instance (ARM64/Graviton) to provide
# outbound internet access for private-subnet workloads (EKS worker nodes,
# RDS patch downloads, etc.).
#
# Architecture:
#   - Single NAT instance in public subnet us-east-2a
#   - Route: private-rt 0.0.0.0/0 → NAT instance primary ENI
#   - SSM Session Manager enabled (no port 22 needed for management)
#
# ⚠ SINGLE POINT OF FAILURE (DEV):
#   One NAT instance serves both AZs. If it becomes unavailable, all
#   private-subnet egress stops.
#   For production, deploy one instance per AZ (enable_ha = true pattern).
#
# Dependencies:
#   shared-infra → VPC, public subnets, private route table, private subnet CIDRs
#
# Usage:
#   terragrunt plan
#   terragrunt apply
# ==============================================================================

include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform//modules/nat"
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
    vpc_id                 = "vpc-mock-id"
    public_subnet_ids      = ["subnet-mock-pub-1", "subnet-mock-pub-2"]
    private_subnet_cidrs   = ["10.0.10.0/24", "10.0.11.0/24"]
    private_route_table_id = "rtb-mock-private"
  }
}

inputs = {
  # Enabled for dev environment. Flip to false to disable NAT instance.
  enabled = true

  tags = {  
    Environment = local.env_vars.env
    Project     = local.common_vars.project_name
    ManagedBy   = "Terragrunt"
  }
  
  project_name = local.common_vars.project_name
  env          = local.env_vars.env
  account_id   = local.env_vars.account_id

  vpc_id                 = dependency.shared_infra.outputs.vpc_id
  public_subnet_id       = dependency.shared_infra.outputs.public_subnet_ids[0]
  private_subnet_cidrs   = dependency.shared_infra.outputs.private_subnet_cidrs
  private_route_table_id = dependency.shared_infra.outputs.private_route_table_id

  # t4g.nano: ARM/Graviton — required by the fck-nat ARM64 AMI
  instance_type = "t4g.nano"

  # Optional SSH key for break-glass access (prefer SSM Session Manager)
  # key_name = "nat-key"

  # Allow SSH from the bastion's public IP
  allowed_ssh_cidrs = []

  enable_ssm        = true
  enable_cloudwatch = true
}