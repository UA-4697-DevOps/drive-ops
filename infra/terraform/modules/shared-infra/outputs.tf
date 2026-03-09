# --- Networking (VPC) ---
output "vpc_id" {
  description = "The ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "The CIDR block of the VPC"
  value       = module.vpc.vpc_cidr
}

output "public_subnet_ids" {
  description = "List of public subnet IDs for internet-facing workloads"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "List of private subnet IDs for internal workloads"
  value       = module.vpc.private_subnet_ids
}

output "sg_app_id" {
  description = "Security group ID for application services"
  value       = module.vpc.sg_app_id
}

output "sg_db_id" {
  description = "Security group ID for database workloads"
  value       = module.vpc.sg_db_id
}

output "sg_alb_id" {
  description = "Security group ID for Application Load Balancer"
  value       = module.vpc.sg_alb_id
}

output "private_route_table_id" {
  description = "ID of the private subnet route table — passed to the NAT module to add the default route"
  value       = module.vpc.private_route_table_id
}

output "private_subnet_cidrs" {
  description = "CIDR blocks of private subnets — passed to the NAT module SG ingress allowlist"
  value       = module.vpc.private_subnet_cidrs
}

# --- Messaging (SQS) ---
output "sqs_urls" {
  description = "Map of all SQS Queue URLs for service environment variables"
  value = {
    trip_created    = module.trip_created.queue_url
    driver_assigned = module.driver_assigned.queue_url
    trip_completed  = module.trip_completed.queue_url
  }
}

# Required for IAM Policies (Resources)
output "sqs_arns" {
  description = "Map of all SQS Queue ARNs for IAM permission policies"
  value = {
    trip_created    = module.trip_created.queue_arn
    driver_assigned = module.driver_assigned.queue_arn
    trip_completed  = module.trip_completed.queue_arn
  }
}

# Required for Monitoring Module to attach alarms
output "sqs_names" {
  description = "Map of SQS Queue Names for CloudWatch Alarms"
  value = {
    trip_created    = module.trip_created.queue_name
    driver_assigned = module.driver_assigned.queue_name
    trip_completed  = module.trip_completed.queue_name
  }
}

output "sqs_policy_arns" {
  description = "Map of IAM policy ARNs for granular service permissions"
  value = {
    trip_created_publisher    = module.trip_created.publisher_policy_arn
    trip_created_consumer     = module.trip_created.consumer_policy_arn
    driver_assigned_publisher = module.driver_assigned.publisher_policy_arn
    driver_assigned_consumer  = module.driver_assigned.consumer_policy_arn
    trip_completed_publisher  = module.trip_completed.publisher_policy_arn
    trip_completed_consumer   = module.trip_completed.consumer_policy_arn
  }
}

# --- Container Registry (ECR) ---
output "ecr_repository_urls" {
  description = "Map of ECR repository URLs for CI/CD pipelines"
  value = {
    client_gateway = module.ecr_client_gateway.repository_url
    driver_service = module.ecr_driver_service.repository_url
    trip_service   = module.ecr_trip_service.repository_url
    web_client     = module.ecr_web_client.repository_url
  }
}

output "ecr_repository_arns" {
  description = "Map of ECR repository ARNs for IAM policy scoping"
  value = {
    client_gateway = module.ecr_client_gateway.repository_arn
    driver_service = module.ecr_driver_service.repository_arn
    trip_service   = module.ecr_trip_service.repository_arn
    web_client     = module.ecr_web_client.repository_arn
  }
}

output "ecr_iam_role_arns" {
  description = "IAM Role ARNs for GitHub Actions OIDC authentication"
  value = {
    client_gateway = module.ecr_client_gateway.role_arn
    driver_service = module.ecr_driver_service.role_arn
    trip_service   = module.ecr_trip_service.role_arn
    web_client     = module.ecr_web_client.role_arn
  }
}

output "ecr_iam_role_names" {
  description = "IAM Role names for GitHub Actions (for policy attachment)"
  value = {
    client_gateway = module.ecr_client_gateway.role_name
    driver_service = module.ecr_driver_service.role_name
    trip_service   = module.ecr_trip_service.role_name
    web_client     = module.ecr_web_client.role_name
  }
}

# --- Encryption (KMS) ---
output "kms_key_arn" {
  description = "ARN of the customer-managed KMS key (null when enable_kms = false)"
  value       = var.enable_kms ? aws_kms_key.cmk[0].arn : null
}

output "kms_key_id" {
  description = "ID of the customer-managed KMS key (null when enable_kms = false)"
  value       = var.enable_kms ? aws_kms_key.cmk[0].key_id : null
}

# --- Secrets ---
output "rds_secret_arn" {
  description = "ARN of the Secrets Manager secret for RDS credentials"
  value       = module.rds_secrets.rds_master_secret_arn
}

output "rds_secret_name" {
  description = "Friendly name of the RDS secret"
  value       = module.rds_secrets.rds_master_secret_name
}

output "discord_secret_arn" {
  description = "ARN of the Secrets Manager secret containing the Discord Webhook URL"
  value       = module.rds_secrets.discord_secret_arn
}

output "telegram_bot_secret_arn" {
  description = "ARN of the Secrets Manager secret containing the Telegram Bot Token"
  value       = module.rds_secrets.telegram_bot_secret_arn
}
