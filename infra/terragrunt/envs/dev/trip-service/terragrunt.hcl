include "root" {
  # Inherit common settings from the root.hcl file
  path = find_in_parent_folders("root.hcl")
}

terraform {
  # Points to the module responsible for service-specific ECR and IAM
  source = "../../../../terraform/modules//ecr"
}

dependency "shared_infra" {
  # Link to the shared infrastructure for potential future dependencies
  config_path = "../shared-infra"

  # Mocks remain for successful planning/validation
  mock_outputs = {
    vpc_id             = "vpc-mock-id"
    private_subnet_ids = ["subnet-mock-1", "subnet-mock-2"]
  }

  mock_outputs_allowed_terraform_commands = ["plan", "validate"]
}

inputs = {
  # These are the ONLY variables currently accepted by the ECR module
  repository_name = "trip-service"
  github_repo     = "UA-4697-DevOps/drive-ops"
}
