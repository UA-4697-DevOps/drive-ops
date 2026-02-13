include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules//compute"
}

dependency "shared_infra" {
  config_path = "../shared-infra"

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
  mock_outputs = {
    vpc_id            = "vpc-00000000000000000"
    public_subnet_ids = ["subnet-00000000000000000", "subnet-11111111111111111"]
    sg_app_id         = "sg-00000000000000000"
  }
}

inputs = {
  name      = "drive-ops-dev-trip-service"
  ami       = "ami-0f9c27b471bdcd702"
  vpc_id    = dependency.shared_infra.outputs.vpc_id
  subnet_id = dependency.shared_infra.outputs.public_subnet_ids[0]

  # Attach sg-app so RDS (sg-db) accepts connections from this instance
  additional_security_group_ids = [dependency.shared_infra.outputs.sg_app_id]

  instance_type               = "t3.micro"
  associate_public_ip_address = true

  # Open trip-service application port
  app_port                     = 8081
  allowed_app_port_cidr_blocks = ["0.0.0.0/0"]

  tags = {
    Service   = "trip-service"
    Component = "ec2"
  }
}
