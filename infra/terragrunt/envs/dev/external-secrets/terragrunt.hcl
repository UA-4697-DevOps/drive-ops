include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform//modules/external-secrets"
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

dependency "eks" {
  config_path = "../eks"

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init", "destroy"]
  mock_outputs_merge_strategy_with_state  = "shallow"

  mock_outputs = {
    oidc_provider_arn = "arn:aws:iam::123456789012:oidc-provider/mock"
    oidc_provider_url = "oidc.eks.us-east-2.amazonaws.com/id/mock"
  }
}

inputs = {
  project_name      = local.common_vars.project_name
  env               = local.env_vars.env
  account_id        = local.env_vars.account_id
  aws_region        = try(local.env_vars.aws_region, local.common_vars.aws_region)
  oidc_provider_arn = dependency.eks.outputs.oidc_provider_arn
  oidc_provider_url = dependency.eks.outputs.oidc_provider_url
  eso_namespace     = "external-secrets"

  tags = {
    Component = "external-secrets"
  }
}
