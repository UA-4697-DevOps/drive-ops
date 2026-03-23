include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules//compute"
}

# --- Locals ---
# common_vars / env_vars are referenced here only to construct the `name` tag.
# project_name, env, account_id, and tags are already injected as Terraform
# variable inputs by root.hcl and do not need to be repeated as inputs here.
# svc provides shared mock outputs for the dependency blocks below.
locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
  svc         = read_terragrunt_config(find_in_parent_folders("_service_common.hcl"))
}

# --- Dependencies ---

dependency "shared_infra" {
  config_path = "../shared-infra"

  mock_outputs_allowed_terraform_commands = local.svc.locals.allowed_commands
  mock_outputs_merge_strategy_with_state  = "shallow"
  mock_outputs                            = local.svc.locals.shared_infra_mock_outputs
}

# RDS dependency kept for explicit apply/destroy ordering
dependency "rds" {
  config_path                             = "../rds"
  mock_outputs_allowed_terraform_commands = local.svc.locals.allowed_commands
  mock_outputs                            = {}
}

# --- Inputs ---
# Note: project_name, env, account_id, tags injected by root.hcl.

inputs = {
  # Identity
  name         = "Training-${local.common_vars.project_name}-${local.env_vars.env}-trip-service"
  service_name = "trip-service"

  # EC2 Configuration
  ami                         = "ami-050352a65e954abb1"
  instance_type               = "t3.micro"
  associate_public_ip_address = true

  # Network Placement
  vpc_id    = dependency.shared_infra.outputs.vpc_id
  subnet_id = dependency.shared_infra.outputs.public_subnet_ids[0]

  # Security Groups
  additional_security_group_ids = [dependency.shared_infra.outputs.sg_app_id]

  # ECR
  ecr_repository_url = dependency.shared_infra.outputs.ecr_repository_urls.trip_service

  # IAM: Secrets Manager access
  iam_secret_arns = [dependency.shared_infra.outputs.rds_secret_arn]

  # IAM: SQS access (all three queues)
  iam_sqs_arns = [
    dependency.shared_infra.outputs.sqs_arns["trip_created"],
    dependency.shared_infra.outputs.sqs_arns["driver_assigned"],
    dependency.shared_infra.outputs.sqs_arns["trip_completed"],
  ]

  # Application Port
  app_port                     = 8081
  allowed_app_port_cidr_blocks = ["0.0.0.0/0"]

  tags = {
    Service   = "trip-service"
    Component = "ec2"
  }
}
