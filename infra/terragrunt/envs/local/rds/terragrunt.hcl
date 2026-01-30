include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules/rds"
}

dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id             = "vpc-123456"
    private_subnet_ids = ["private-subnet-1", "private-subnet-2"]
    public_subnet_ids  = ["public-subnet-1", "public-subnet-2"]
    sg_db_id           = "sg-mock"
  }

  # Allow mock outputs for these commands (when VPC not deployed yet)
  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
}

dependency "secrets" {
  config_path = "../secrets"

  mock_outputs = {
    rds_master_password = "mock-password"
  }

  # Allow mock outputs for these commands (when secrets not deployed yet)
  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

inputs = {
  db_name                 = "drive_ops_${local.env_vars.env}"
  vpc_id                  = dependency.vpc.outputs.vpc_id
  private_subnet_ids      = dependency.vpc.outputs.private_subnet_ids
  db_security_group_id    = dependency.vpc.outputs.sg_db_id
  master_username         = "postgres"
  master_password         = dependency.secrets.outputs.rds_master_password
  engine_version          = "15.15"
  instance_class          = "db.t3.micro"
  allocated_storage       = 20
  backup_retention_period = 1
  multi_az                = false
  deletion_protection     = false
  skip_final_snapshot     = true
}