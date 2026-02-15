include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  # Points to the reusable RDS Terraform module
  source = "../../../../terraform/modules/rds"
}

# Consolidated dependency: RDS now only depends on shared-infra
dependency "shared_infra" {
  config_path = "../shared-infra"

  # Mock outputs allow running 'plan' and 'validate' even before resources are created
  mock_outputs = {
    vpc_id             = "vpc-12345678"
    private_subnet_ids = ["subnet-123", "subnet-456"]
    sg_db_id           = "sg-00000000"
    rds_secret_arn     = "arn:aws:secretsmanager:us-east-2:123456789012:secret:mock-rds-secret"
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init", "destroy"]
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

inputs = {
  # Database naming based on environment
  db_name = "drive_ops_${local.env_vars.env}"

  # Networking data retrieved from shared-infra dependency
  vpc_id               = dependency.shared_infra.outputs.vpc_id
  private_subnet_ids   = dependency.shared_infra.outputs.private_subnet_ids
  db_security_group_id = dependency.shared_infra.outputs.sg_db_id

  # Master password retrieved from Secrets Manager managed by shared-infra
  rds_master_secret_id = dependency.shared_infra.outputs.rds_secret_arn

  # Instance Configuration
  engine_version          = "15.10" # Verified version for us-east-2
  instance_class          = "db.t3.micro"
  allocated_storage       = 20
  backup_retention_period = 1
  multi_az                = false
  deletion_protection     = false
  skip_final_snapshot     = true

  # Tags are merged with common tags from global configuration
  tags = merge(local.common_vars.common_tags, {
    Component = "database"
    Env       = local.env_vars.env
  })
}
