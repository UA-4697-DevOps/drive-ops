include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform/modules//ecs-service"
}

dependency "shared_infra" {
  config_path = "../shared-infra"

  mock_outputs = {
    vpc_id             = "vpc-123456"
    private_subnet_ids = ["subnet-1", "subnet-2"]
    sg_app_id          = "sg-123456"
    all_queue_arns = {
      trip_created    = "arn:aws:sqs:us-east-2:123456789012:queue/mock-trip-created"
      driver_assigned = "arn:aws:sqs:us-east-2:123456789012:queue/mock-driver-assigned"
      trip_completed  = "arn:aws:sqs:us-east-2:123456789012:queue/mock-trip-completed"
    }
    all_queue_urls = {
      trip_created    = "https://sqs.us-east-2.amazonaws.com/123456789012/mock-trip-created"
      driver_assigned = "https://sqs.us-east-2.amazonaws.com/123456789012/mock-driver-assigned"
      trip_completed  = "https://sqs.us-east-2.amazonaws.com/123456789012/mock-trip-completed"
    }
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
}

dependency "rds" {
  config_path = "../rds"

  mock_outputs = {
    db_address = "mock-rds.us-east-2.rds.amazonaws.com"
    db_port    = 5432
    db_name    = "drive_ops_dev"
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

dependency "ecr" {
  config_path = "../driver-service-ecr"

  mock_outputs = {
    repository_url = "123456789012.dkr.ecr.us-east-2.amazonaws.com/driver-service"
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

inputs = {
  service_name = "driver-service"

  vpc_id              = dependency.shared_infra.outputs.vpc_id
  private_subnet_ids  = dependency.shared_infra.outputs.private_subnet_ids
  security_group_id   = dependency.shared_infra.outputs.sg_app_id

  ecr_repository_url = dependency.ecr.outputs.repository_url
  image_tag          = "latest"

  container_port   = 8082
  container_cpu    = 256
  container_memory = 512
  desired_count    = 1

  environment_variables = {
    PYTHONUNBUFFERED           = "1"
    PYTHONPATH                 = "/app/src"
    AWS_REGION                 = local.env_vars.aws_region
    SQS_TRIP_CREATED_URL       = dependency.shared_infra.outputs.all_queue_urls["trip_created"]
    SQS_DRIVER_ASSIGNED_URL    = dependency.shared_infra.outputs.all_queue_urls["driver_assigned"]
    SQS_TRIP_COMPLETED_URL     = dependency.shared_infra.outputs.all_queue_urls["trip_completed"]
  }

  secrets = {
    DATABASE_URL = {
      valueFrom = dependency.secrets.outputs.rds_master_secret_arn
    }
  }

  sqs_queue_arns = [
    dependency.shared_infra.outputs.all_queue_arns["trip_created"],
    dependency.shared_infra.outputs.all_queue_arns["driver_assigned"],
    dependency.shared_infra.outputs.all_queue_arns["trip_completed"]
  ]

  secrets_arns = [
    dependency.secrets.outputs.rds_master_secret_arn
  ]

  health_check_path         = "/health"
}
