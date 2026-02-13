include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

terraform {
  # ADD THE DOUBLE SLASH HERE:
  source = "../../../../terraform//modules/observability"
}

dependency "secrets" {
  config_path = "../secrets"
  
  mock_outputs = {
    discord_webhook_secret_arn = "arn:aws:secretsmanager:us-east-2:123456789012:secret:mock-arn"
  }
  mock_outputs_allowed_terraform_commands = ["plan", "validate", "apply"]
}

inputs = {
  project_name               = include.root.locals.project_name
  environment                = include.root.locals.env
  service_names              = include.root.locals.common_vars.monitored_services
  discord_webhook_secret_arn = dependency.secrets.outputs.discord_webhook_secret_arn
}
