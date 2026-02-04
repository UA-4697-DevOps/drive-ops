include "root" {
  # Inherit common settings from the root.hcl file
  path = find_in_parent_folders("root.hcl")
}

terraform {
  # Points to the module responsible for service-specific IAM roles (OIDC)
  # Ensure your ECR module supports a "create_repo = false" flag or use a dedicated IAM module
  source = "../../../../terraform/modules//ecr"
}

dependency "shared_infra" {
  # Link to the shared infrastructure for network and common resource data
  config_path = "../shared-infra"

  # Mock outputs allow 'terragrunt plan' to succeed even if shared-infra is not yet applied
  mock_outputs = {
    vpc_id             = "vpc-mock-id"
    private_subnet_ids = ["subnet-mock-1", "subnet-mock-2"]
  }
  
  # Mocking is only active during planning and validation phases
  mock_outputs_allowed_terraform_commands = ["plan", "validate"]
}

inputs = {
  service_name = "trip-service"
  
  # Networking data retrieved from the shared_infra dependency
  vpc_id     = dependency.shared_infra.outputs.vpc_id
  subnet_ids = dependency.shared_infra.outputs.private_subnet_ids 

  # CI/CD settings for GitHub Actions OIDC authentication
  repository_name    = "trip-service"
  github_repo        = "Davlit-ops/drive-ops"
  account_id         = "969283154407"
  
  # Secure, keyless authentication ARN for GitHub Actions
  oidc_provider_arn  = "arn:aws:iam::969283154407:oidc-provider/token.actions.githubusercontent.com"
}
