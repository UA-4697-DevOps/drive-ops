include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules//ec2-docker-host"
}

dependency "shared_infra" {
  config_path = "../shared-infra"

  mock_outputs = {
    vpc_id             = "vpc-mock"
    public_subnet_ids  = ["subnet-mock-1", "subnet-mock-2"]
    sg_app_id          = "sg-mock"
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

inputs = {
  service_name      = "driver-service"
  vpc_id            = dependency.shared_infra.outputs.vpc_id
  subnet_id         = dependency.shared_infra.outputs.public_subnet_ids[0]
  security_group_id = dependency.shared_infra.outputs.sg_app_id
  instance_type     = "t3.micro"
  key_name          = null
}
