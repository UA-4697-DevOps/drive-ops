# terraform/modules/sqs-messaging/outputs.tf

# ==========================================
# Trip Created Queue Outputs
# ==========================================

output "trip_created_queue_url" {
  description = "URL of the trip-created main queue"
  value       = module.trip_created.queue_url
}

output "trip_created_queue_arn" {
  description = "ARN of the trip-created main queue"
  value       = module.trip_created.queue_arn
}

output "trip_created_dlq_url" {
  description = "URL of the trip-created DLQ"
  value       = module.trip_created.dlq_url
}

output "trip_created_dlq_arn" {
  description = "ARN of the trip-created DLQ"
  value       = module.trip_created.dlq_arn
}

output "trip_created_consumer_policy_arn" {
  description = "ARN of the IAM policy for trip-created consumers"
  value       = module.trip_created.consumer_policy_arn
}

output "trip_created_publisher_policy_arn" {
  description = "ARN of the IAM policy for trip-created publishers"
  value       = module.trip_created.publisher_policy_arn
}

# ==========================================
# Driver Assigned Queue Outputs
# ==========================================

output "driver_assigned_queue_url" {
  description = "URL of the driver-assigned main queue"
  value       = module.driver_assigned.queue_url
}

output "driver_assigned_queue_arn" {
  description = "ARN of the driver-assigned main queue"
  value       = module.driver_assigned.queue_arn
}

output "driver_assigned_dlq_url" {
  description = "URL of the driver-assigned DLQ"
  value       = module.driver_assigned.dlq_url
}

output "driver_assigned_dlq_arn" {
  description = "ARN of the driver-assigned DLQ"
  value       = module.driver_assigned.dlq_arn
}

output "driver_assigned_consumer_policy_arn" {
  description = "ARN of the IAM policy for driver-assigned consumers"
  value       = module.driver_assigned.consumer_policy_arn
}

output "driver_assigned_publisher_policy_arn" {
  description = "ARN of the IAM policy for driver-assigned publishers"
  value       = module.driver_assigned.publisher_policy_arn
}

# ==========================================
# Trip Completed Queue Outputs
# ==========================================

output "trip_completed_queue_url" {
  description = "URL of the trip-completed main queue"
  value       = module.trip_completed.queue_url
}

output "trip_completed_queue_arn" {
  description = "ARN of the trip-completed main queue"
  value       = module.trip_completed.queue_arn
}

output "trip_completed_dlq_url" {
  description = "URL of the trip-completed DLQ"
  value       = module.trip_completed.dlq_url
}

output "trip_completed_dlq_arn" {
  description = "ARN of the trip-completed DLQ"
  value       = module.trip_completed.dlq_arn
}

output "trip_completed_consumer_policy_arn" {
  description = "ARN of the IAM policy for trip-completed consumers"
  value       = module.trip_completed.consumer_policy_arn
}

output "trip_completed_publisher_policy_arn" {
  description = "ARN of the IAM policy for trip-completed publishers"
  value       = module.trip_completed.publisher_policy_arn
}

# ==========================================
# Aggregated Outputs (for convenience)
# ==========================================

output "all_queue_urls" {
  description = "Map of all main queue URLs"
  value = {
    trip_created     = module.trip_created.queue_url
    driver_assigned  = module.driver_assigned.queue_url
    trip_completed   = module.trip_completed.queue_url
  }
}

output "all_queue_arns" {
  description = "Map of all main queue ARNs"
  value = {
    trip_created     = module.trip_created.queue_arn
    driver_assigned  = module.driver_assigned.queue_arn
    trip_completed   = module.trip_completed.queue_arn
  }
}

output "all_dlq_arns" {
  description = "Map of all DLQ ARNs"
  value = {
    trip_created     = module.trip_created.dlq_arn
    driver_assigned  = module.driver_assigned.dlq_arn
    trip_completed   = module.trip_completed.dlq_arn
  }
}
