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
  value = {
    trip_created    = module.trip_created.queue_url
    driver_assigned = module.driver_assigned.queue_url
    trip_completed  = module.trip_completed.queue_url
  }
}

output "all_queue_arns" {
  description = "Map of all queue ARNs"
  value = {
    trip_created    = module.trip_created.queue_arn
    driver_assigned = module.driver_assigned.queue_arn
    trip_completed  = module.trip_completed.queue_arn
  }
}

output "all_dlq_arns" {
  description = "Map of all DLQ ARNs"
  value = {
    trip_created    = module.trip_created.dlq_arn
    driver_assigned = module.driver_assigned.dlq_arn
    trip_completed  = module.trip_completed.dlq_arn
  }
}

output "trip_created_queue_url" {
  description = "URL of trip-created queue"
  value       = module.trip_created.queue_url
}

output "driver_assigned_queue_url" {
  description = "URL of driver-assigned queue"
  value       = module.driver_assigned.queue_url
}

output "trip_completed_queue_url" {
  description = "URL of trip-completed queue"
  value       = module.trip_completed.queue_url
}

output "trip_created_consumer_policy_arn" {
  description = "ARN of trip-created consumer policy"
  value       = module.trip_created.consumer_policy_arn
}

output "trip_created_publisher_policy_arn" {
  description = "ARN of trip-created publisher policy"
  value       = module.trip_created.publisher_policy_arn
}

output "driver_assigned_consumer_policy_arn" {
  description = "ARN of driver-assigned consumer policy"
  value       = module.driver_assigned.consumer_policy_arn
}

output "driver_assigned_publisher_policy_arn" {
  description = "ARN of driver-assigned publisher policy"
  value       = module.driver_assigned.publisher_policy_arn
}

output "trip_completed_consumer_policy_arn" {
  description = "ARN of trip-completed consumer policy"
  value       = module.trip_completed.consumer_policy_arn
}

output "trip_completed_publisher_policy_arn" {
  description = "ARN of trip-completed publisher policy"
  value       = module.trip_completed.publisher_policy_arn
}
