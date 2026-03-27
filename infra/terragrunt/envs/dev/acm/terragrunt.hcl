include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform//modules/acm"
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

dependency "route53" {
  config_path = "../route53"

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init", "destroy"]
  mock_outputs_merge_strategy_with_state  = "shallow"

  mock_outputs = {
    zone_id = "Z1234567890ABC"
  }
}

inputs = {
  project_name = local.common_vars.project_name
  env          = local.env_vars.env
  domain_name  = "driveops.dukhota.dev"
  zone_id      = dependency.route53.outputs.zone_id

  tags = {
    Component = "acm"
  }
}
