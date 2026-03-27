include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform//modules/route53"
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

inputs = {
  project_name = local.common_vars.project_name
  env          = local.env_vars.env
  domain_name  = "driveops.dukhota.dev"

  tags = {
    Component = "route53"
  }
}
