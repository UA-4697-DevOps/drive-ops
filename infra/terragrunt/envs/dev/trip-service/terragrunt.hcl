include "root" {
  # Inherit common settings from the root.hcl file
  path = find_in_parent_folders("root.hcl")
}

terraform {
  # Points to the module responsible for service-specific ECR and IAM
  source = "../../../../terraform/modules//ecr"
}

inputs = {
  # These are the ONLY variables currently accepted by the ECR module
  repository_name = "trip-service"
  github_repo     = "UA-4697-DevOps/drive-ops"
}
