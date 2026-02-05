# terraform/modules/shared-infra/outputs.tf

# --- VPC Outputs ---
output "vpc_id" {
  description = "The ID of the VPC"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = module.vpc.public_subnet_ids
}

output "sg_app_id" {
  description = "Security group ID for application services"
  value       = module.vpc.sg_app_id
}

output "sg_db_id" {
  description = "Security group ID for database workloads"
  value       = module.vpc.sg_db_id
}

# --- SQS Outputs ---
output "all_queue_urls" {
  description = "Map of all queue URLs"
  value       = module.sqs_messaging.all_queue_urls
}

output "all_queue_arns" {
  description = "Map of all queue ARNs"
  value       = module.sqs_messaging.all_queue_arns
}

output "all_dlq_arns" {
  description = "Map of all DLQ ARNs"
  value       = module.sqs_messaging.all_dlq_arns
}

output "trip_created_queue_url" {
  description = "URL of trip-created queue"
  value       = module.sqs_messaging.trip_created_queue_url
}

output "driver_assigned_queue_url" {
  description = "URL of driver-assigned queue"
  value       = module.sqs_messaging.driver_assigned_queue_url
}

output "trip_completed_queue_url" {
  description = "URL of trip-completed queue"
  value       = module.sqs_messaging.trip_completed_queue_url
}

output "trip_created_consumer_policy_arn" {
  description = "ARN of trip-created consumer policy"
  value       = module.sqs_messaging.trip_created_consumer_policy_arn
}

output "trip_created_publisher_policy_arn" {
  description = "ARN of trip-created publisher policy"
  value       = module.sqs_messaging.trip_created_publisher_policy_arn
}

output "driver_assigned_consumer_policy_arn" {
  description = "ARN of driver-assigned consumer policy"
  value       = module.sqs_messaging.driver_assigned_consumer_policy_arn
}

output "driver_assigned_publisher_policy_arn" {
  description = "ARN of driver-assigned publisher policy"
  value       = module.sqs_messaging.driver_assigned_publisher_policy_arn
}

output "trip_completed_consumer_policy_arn" {
  description = "ARN of trip-completed consumer policy"
  value       = module.sqs_messaging.trip_completed_consumer_policy_arn
}

output "trip_completed_publisher_policy_arn" {
  description = "ARN of trip-completed publisher policy"
  value       = module.sqs_messaging.trip_completed_publisher_policy_arn
}
