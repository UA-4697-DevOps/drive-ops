# ==============================================================================
# VPN (OpenVPN) – TERRAGRUNT STACK (DEV)
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
  
  # Automatically detect the current public IP of the operator (you)
  my_ip       = "${chomp(run_cmd("curl", "-s", "https://ifconfig.me"))}/32"
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
  public_subnet_id = dependency.shared_infra.outputs.public_subnet_ids[0]

  # Graviton-based instance for hardware-accelerated encryption
  instance_type    = "t4g.micro"
  vpn_client_cidr  = "10.8.0.0/24"

  # --- SECURITY GROUP RULES ---
  # These rules are passed to the nested security-group module.
  # Keys are required for the for_each loop in the module.
  
  ingress_rules = [
    {
      key         = "vpn_udp"
      description = "Allow OpenVPN traffic from operators current IP"
      from_port   = 1194
      to_port     = 1194
      protocol    = "udp"
      cidr_blocks = [local.my_ip]
    }
  ]

  egress_rules = [
    {
      key         = "all_outbound"
      description = "Allow all outbound traffic (essential for VPN client routing)"
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_blocks = ["0.0.0.0/0"]
    }
  ]
  # ------------------------------

  kms_key_arn = try(dependency.shared_infra.outputs.kms_key_arn, null)

  tags = {
    Component = "vpn"
  }
}