# _service_common.hcl
#
# Shared Terragrunt partial config consumed by all application services
# (trip-service, driver-service, client-gateway) via read_terragrunt_config().
#
# Provides canonical mock output values for the shared-infra and rds
# dependencies so each service does not need to duplicate them inline.
#
# Usage in service terragrunt.hcl:
#
#   locals {
#     common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
#     env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
#     svc         = read_terragrunt_config(find_in_parent_folders("_service_common.hcl"))
#   }
#
#   dependency "shared_infra" {
#     config_path                            = "../shared-infra"
#     mock_outputs_allowed_terraform_commands = local.svc.locals.allowed_commands
#     mock_outputs_merge_strategy_with_state  = "shallow"
#     mock_outputs                            = local.svc.locals.shared_infra_mock_outputs
#   }
#
#   dependency "rds" {
#     config_path                             = "../rds"
#     mock_outputs_allowed_terraform_commands = local.svc.locals.allowed_commands
#     mock_outputs                            = {}
#   }

locals {
  # Commands for which mock outputs are allowed (avoids real-state lookup)
  allowed_commands = ["validate", "plan", "init", "destroy"]

  # Canonical mock outputs for the shared-infra module.
  # These cover all service keys so any service can reference its own ECR URL.
  shared_infra_mock_outputs = {
    vpc_id             = "vpc-mock-id"
    public_subnet_ids  = ["subnet-mock-1", "subnet-mock-2"]
    private_subnet_ids = ["subnet-mock-priv-1", "subnet-mock-priv-2"]
    sg_app_id          = "sg-mock-app"

    # All known ECR repository keys
    ecr_repository_urls = {
      trip_service   = "000000000000.dkr.ecr.us-east-2.amazonaws.com/trip-service"
      driver_service = "000000000000.dkr.ecr.us-east-2.amazonaws.com/driver-service"
      client_gateway = "000000000000.dkr.ecr.us-east-2.amazonaws.com/client-gateway"
    }

    # SQS ARNs needed by trip-service and driver-service IAM policies
    sqs_arns = {
      trip_created    = "arn:aws:sqs:us-east-2:000:trip-created"
      driver_assigned = "arn:aws:sqs:us-east-2:000:driver-assigned"
      trip_completed  = "arn:aws:sqs:us-east-2:000:trip-completed"
    }

    # Secrets Manager ARN needed by trip-service and driver-service IAM policies
    rds_secret_arn = "arn:aws:secretsmanager:us-east-2:000:secret:mock-secret"
  }
}
