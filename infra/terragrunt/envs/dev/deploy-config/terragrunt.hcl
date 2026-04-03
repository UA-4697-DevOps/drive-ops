include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules//deploy-config"
}

# --- Dependencies: read outputs from existing modules ---

dependency "rds" {
  config_path = "../rds"

  mock_outputs = {
    db_address  = "mock-db.us-east-2.rds.amazonaws.com"
    db_port     = 5432
    db_name     = "drive_ops_dev"
    db_username = "mock_user"
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
}

dependency "shared_infra" {
  config_path = "../shared-infra"

  mock_outputs = {
    sqs_urls = {
      trip_created    = "https://sqs.us-east-2.amazonaws.com/123456789012/trip-created-dev.fifo"
      driver_assigned = "https://sqs.us-east-2.amazonaws.com/123456789012/driver-assigned-dev.fifo"
      trip_completed  = "https://sqs.us-east-2.amazonaws.com/123456789012/trip-completed-dev.fifo"
    }
    ecr_iam_role_names = {
      trip_service = "Training-trip-service-github-actions-role"
    }
    ecr_repository_arns = {
      trip_service = "arn:aws:ecr:us-east-2:123456789012:repository/trip-service"
    }
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
}




dependency "ec2" {
  config_path = "../trip-service"

  mock_outputs = {
    instance_id = "mock_id"
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
}

# Note: project_name, env, aws_region, account_id, and tags are already
# provided by root.hcl's global inputs block — no need to redeclare them.

inputs = {
  # --- SSM Parameters (single map drives all aws_ssm_parameter resources) ---
  ssm_parameters = {
    "trip-service/db-host" = {
      description = "RDS endpoint hostname for TripService"
      type        = "String"
      value       = dependency.rds.outputs.db_address
    }
    "trip-service/db-port" = {
      description = "RDS port for TripService"
      type        = "String"
      value       = tostring(dependency.rds.outputs.db_port)
    }
    "trip-service/db-name" = {
      description = "Database name for TripService"
      type        = "String"
      value       = dependency.rds.outputs.db_name
    }
    "trip-service/db-user" = {
      description = "Database username for TripService"
      type        = "SecureString"
      value       = dependency.rds.outputs.db_username
    }
    "sqs/trip-created-url" = {
      description = "SQS FIFO queue URL for trip-created events"
      type        = "String"
      value       = dependency.shared_infra.outputs.sqs_urls.trip_created
    }
    "sqs/driver-assigned-url" = {
      description = "SQS FIFO queue URL for driver-assigned events"
      type        = "String"
      value       = dependency.shared_infra.outputs.sqs_urls.driver_assigned
    }
    "sqs/trip-completed-url" = {
      description = "SQS FIFO queue URL for trip-completed events"
      type        = "String"
      value       = dependency.shared_infra.outputs.sqs_urls.trip_completed
    }
    "infra/ec2-instance-id" = {
      description = "EC2 instance ID for SSM Run Command targeting"
      type        = "String"
      value       = dependency.ec2.outputs.instance_id
    }
  }

  # --- IAM / Deploy Configuration ---
  rds_secret_arn           = dependency.shared_infra.outputs.rds_master_secret_arn
  service_name             = "trip-service"
  repository_name          = "trip-service"
  ecr_repo_arn             = dependency.shared_infra.outputs.ecr_repository_arns.trip_service
  github_actions_role_name = dependency.shared_infra.outputs.ecr_iam_role_names.trip_service
  ec2_instance_id          = dependency.ec2.outputs.instance_id
}
