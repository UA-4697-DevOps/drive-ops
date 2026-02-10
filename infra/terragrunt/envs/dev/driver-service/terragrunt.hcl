include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules//ec2-docker-host"
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

inputs = {
  service_name      = "driver-service"
  vpc_id            = "vpc-0a1b2c3d4e5f6g7h8"  # TODO: Replace with actual VPC ID
  subnet_id         = "subnet-0a1b2c3d4e5f6g7h8"  # TODO: Replace with actual public subnet ID
  security_group_id = "sg-0a1b2c3d4e5f6g7h8"  # TODO: Replace with actual security group ID
  instance_type     = "t3.micro"
  key_name          = null
}
