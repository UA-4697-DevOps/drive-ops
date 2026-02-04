include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  # Update the path to point to the existing module folder (likely 'vpc')
  # The double slash '//' is used by Terragrunt to separate the repo root from the module path
  source = "../../../../terraform/modules//vpc"
}

inputs = {
  # This follows the "minimal, secure dev environment" requirement
  vpc_cidr = "10.0.0.0/16"

  # These inputs will be passed if your 'vpc' module is updated to accept them
  ecr_repositories = [
    "trip-service",
    "driver-service",
    "client-gateway"
  ]

  account_id  = "969283154407"
  github_repo = "Davlit-ops/drive-ops"
}
