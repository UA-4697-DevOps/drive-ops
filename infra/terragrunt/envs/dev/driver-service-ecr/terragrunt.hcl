include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules//ecr"
}

inputs = {
  repository_name = "driver-service"
  github_repo     = "UA-4697-DevOps/drive-ops"
}
