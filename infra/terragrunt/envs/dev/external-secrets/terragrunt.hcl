include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules//external-secrets"
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

dependency "shared_infra" {
  config_path = "../shared-infra"

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init", "destroy"]
  mock_outputs = {
    oidc_provider_arn = "arn:aws:iam::123456789012:oidc-provider/mock"
    oidc_provider     = "oidc.eks.us-east-2.amazonaws.com/id/mock"
    rds_secret_arn    = "arn:aws:secretsmanager:us-east-2:123456789012:secret:mock"
  }
}

inputs = {
  project_name = local.common_vars.project_name
  env          = local.env_vars.env
  service_name = "driver-service"
  namespace    = local.env_vars.env

  oidc_provider_arn = dependency.shared_infra.outputs.oidc_provider_arn
  oidc_provider     = dependency.shared_infra.outputs.oidc_provider

  secret_arns = [
    dependency.shared_infra.outputs.rds_secret_arn
  ]

  tags = merge(local.common_vars.common_tags, {
    Service   = "driver-service"
    Component = "external-secrets"
    Env       = local.env_vars.env
  })
}
