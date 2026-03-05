include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules//tag-auditor"
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

inputs = {
  project_name  = local.common_vars.project_name
  env           = local.env_vars.env
  account_id    = local.env_vars.account_id
  
  # Тимчасово хардкодимо, щоб обійти зламаний стейт моніторингу
  sns_topic_arn = "arn:aws:sns:us-east-2:000000000000:drive-ops-dev-alerts"

  lambda_functions = {
    "tag-auditor" = {
      handler     = "tag_auditor.lambda_handler"
      description = "Audits resources via EventBridge"
      schedule    = "rate(24 hours)"
      memory_size = 128
    },
    "tag-cleanup" = {
      handler     = "cleanup.lambda_handler"
      description = "Clean up resources"
      memory_size = 256
    }
  }
}