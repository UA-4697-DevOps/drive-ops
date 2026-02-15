include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules//compute"
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
    vpc_id            = "vpc-mock-id"
    public_subnet_ids = ["subnet-mock-1", "subnet-mock-2"]
    sg_app_id         = "sg-mock-app"

    # Mocks for ECR
    ecr_repository_urls = {
      trip_service = "000000000000.dkr.ecr.us-east-2.amazonaws.com/trip-service"
    }

    # Mocks for SQS ARNs (Needed for IAM policies)
    sqs_arns = {
      trip_created    = "arn:aws:sqs:us-east-2:000:trip-created"
      driver_assigned = "arn:aws:sqs:us-east-2:000:driver-assigned"
      trip_completed  = "arn:aws:sqs:us-east-2:000:trip-completed"
    }

    # Mock for Secret ARN (Needed for IAM policies)
    rds_secret_arn = "arn:aws:secretsmanager:us-east-2:000:secret:mock-secret"
  }
}

# RDS dependency kept for explicit ordering/outputs if needed later
dependency "rds" {
  config_path                             = "../rds"
  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
  mock_outputs                            = {}
}

# --- Inputs ---

inputs = {
  # Context
  name         = "Training-${local.common_vars.project_name}-${local.env_vars.env}-trip-service"
  project_name = local.common_vars.project_name
  env          = local.env_vars.env
  service_name = "trip-service"
  account_id   = local.env_vars.account_id

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

  # --- IAM Permissions ---

  # 1. Secret Access: Use the ARN exported from shared-infra
  iam_secret_arns = [
    dependency.shared_infra.outputs.rds_secret_arn
  ]

  # 2. SQS Access: Use the ARNs exported from shared-infra
  iam_sqs_arns = [
    dependency.shared_infra.outputs.sqs_arns["trip_created"],
    dependency.shared_infra.outputs.sqs_arns["driver_assigned"],
    dependency.shared_infra.outputs.sqs_arns["trip_completed"]
  ]

  # Application Port
  app_port                     = 8081
  allowed_app_port_cidr_blocks = ["0.0.0.0/0"]

  tags = {
    Service   = "trip-service"
    Component = "ec2"
  }
}
