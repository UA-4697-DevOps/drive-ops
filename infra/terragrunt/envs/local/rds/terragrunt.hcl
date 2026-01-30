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
    sg_db_id           = "sg-1242414124214214124"
  }
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
  engine_version          = "15.15"
  instance_class          = "db.t3.micro"
  allocated_storage       = 20
  backup_retention_period = 1
  multi_az                = false
  deletion_protection     = false
  skip_final_snapshot     = true
}