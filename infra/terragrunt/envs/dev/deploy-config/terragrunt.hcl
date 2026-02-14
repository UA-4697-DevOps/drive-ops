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
    trip_created_queue_url    = "https://sqs.us-east-2.amazonaws.com/123456789012/trip-created-dev.fifo"
    driver_assigned_queue_url = "https://sqs.us-east-2.amazonaws.com/123456789012/driver-assigned-dev.fifo"
    trip_completed_queue_url  = "https://sqs.us-east-2.amazonaws.com/123456789012/trip-completed-dev.fifo"
    ecr_iam_role_names = {
      trip_service = "trip-service-github-actions-role"
    }
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
}

dependency "secrets" {
  config_path = "../secrets"

  mock_outputs = {
    rds_master_secret_arn = "arn:aws:secretsmanager:us-east-2:123456789012:secret:mock-secret"
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
  # Database config (wired from RDS module outputs)
  db_host = dependency.rds.outputs.db_address
  db_port = dependency.rds.outputs.db_port
  db_name = dependency.rds.outputs.db_name
  db_user = dependency.rds.outputs.db_username

  # RDS secret ARN (from secrets module)
  rds_secret_arn = dependency.secrets.outputs.rds_master_secret_arn

  # SQS queue URLs (from shared-infra module)
  sqs_trip_created_url    = dependency.shared_infra.outputs.trip_created_queue_url
  sqs_driver_assigned_url = dependency.shared_infra.outputs.driver_assigned_queue_url
  sqs_trip_completed_url  = dependency.shared_infra.outputs.trip_completed_queue_url

  # ECR / GitHub Actions role (from shared-infra ECR outputs)
  repository_name          = "trip-service"
  github_actions_role_name = dependency.shared_infra.outputs.ecr_iam_role_names.trip_service

  ec2_instance_id = dependency.ec2.outputs.instance_id
}
